### welfare-fetch-to-s3 ###
import os, json, time, datetime, urllib.parse
import boto3
from botocore.config import Config
import urllib.request
import xml.etree.ElementTree as ET
import ssl

# ===== 환경 변수 =====
S3_BUCKET    = os.environ["S3_BUCKET"]
API_ENDPOINT = os.environ["API_ENDPOINT"]
SERVICE_KEY  = os.environ["SERVICE_KEY"]   
PATH_PREFIX  = os.environ.get("PATH_PREFIX", "raw")
TIME_OFFSET  = int(os.environ.get("TIME_OFFSET_HOURS", "9"))

# 페이징/조기 종료 파라미터
ROWS_PER_PAGE = int(os.environ.get("ROWS_PER_PAGE", "100"))   # 100 권장(안정 확인 후 200)
PAGE_LIMIT    = int(os.environ.get("PAGE_LIMIT", "5"))        # 실행당 최대 페이지 수
STOP_IF_OLDER_THAN_DAYS = int(os.environ.get("STOP_IF_OLDER_THAN_DAYS", "0"))  # 0=미사용시 주의

s3 = boto3.client("s3", config=Config(retries={"max_attempts": 3, "mode": "standard"}))

# ===== 유틸 =====
def _now_tz(offset_h: int):
    now_utc = datetime.datetime.utcnow()
    return now_utc + datetime.timedelta(hours=offset_h)

def _encode_service_key_once(raw_key: str) -> str:
    # 이미 % 가 들어있으면 인코딩된 것으로 간주(이중 인코딩 방지)
    return raw_key if "%" in raw_key else urllib.parse.quote(raw_key, safe="")

def _build_url(endpoint: str, params: dict) -> str:
    """
    serviceKey는 값 그대로 붙이고, 나머지 파라미터만 urlencode로 인코딩
    (serviceKey 이중 인코딩 방지)
    """
    p = params.copy()
    enc_key = p.pop("serviceKey")
    q = urllib.parse.urlencode(p, doseq=True, safe=":,")
    return f"{endpoint}?serviceKey={enc_key}&{q}" if q else f"{endpoint}?serviceKey={enc_key}"

def _http_get(url, headers=None, timeout=20):
    # 구형 TLS 서버 호환: TLS1.2
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except Exception:
        pass
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    req_headers = {
        "Accept": "application/xml",
        "User-Agent": "Mozilla/5.0 (compatible; LambdaFetcher/1.0)"
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout) as resp:
        return resp.getcode(), resp.headers.get("Content-Type",""), resp.read()

def _parse_xml_to_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    meta = {
        "totalCount": int(root.findtext(".//totalCount") or 0),
        "pageNo": int(root.findtext(".//pageNo") or 1),
        "numOfRows": int(root.findtext(".//numOfRows") or 0),
        "resultCode": root.findtext(".//resultCode") or "",
        "resultMessage": root.findtext(".//resultMessage") or "",
    }
    items = []
    for serv in root.findall(".//servList"):
        item = {}
        for child in list(serv):
            item[child.tag] = (child.text or "").strip()
        items.append(item)
    return meta, items

# ===== 핸들러 =====
def handler(event, context):
    """
    event(선택): {"ctpvNm":"서울특별시","sggNm":"송파구","searchWrd":"국가","arrgOrd":"001"}
    """
    print("EVENT:", json.dumps(event or {}, ensure_ascii=False))
    if not SERVICE_KEY:
        raise ValueError("환경변수 SERVICE_KEY 필요")
    if not API_ENDPOINT:
        raise ValueError("환경변수 API_ENDPOINT 필요")

    # 조기 종료 임계 날짜(옵션): '오늘 - N일'보다 오래된 lastModYmd면 중단
    cutoff = None
    if STOP_IF_OLDER_THAN_DAYS > 0:
        kst_today = _now_tz(TIME_OFFSET).date()
        cutoff = (kst_today - datetime.timedelta(days=STOP_IF_OLDER_THAN_DAYS)).strftime("%Y%m%d")

    now = _now_tz(TIME_OFFSET)
    yyyy, mm, dd, hh = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"), now.strftime("%H")

    saved = {"xml": [], "json": []}
    total_processed = 0

    for page in range(1, PAGE_LIMIT + 1):
        # 기본 파라미터(장애인 + 검색코드003, 최신순)
        base_params = {
            "serviceKey": _encode_service_key_once(SERVICE_KEY),
            "pageNo": str(page),
            "numOfRows": str(ROWS_PER_PAGE),
            "trgterIndvdlArray": "040",
            "srchKeyCode": "003",
            "arrgOrd": "001"
        }
        # 지역/검색어 이벤트로 덮어쓰기
        if event:
            for k in ["ctpvNm", "sggNm", "searchWrd", "arrgOrd"]:
                v = event.get(k)
                if v not in (None, ""):
                    base_params[k] = str(v)

        url = _build_url(API_ENDPOINT, base_params)
        # 민감정보 노출 방지를 위해 URL 전체는 로그에 남기지 않음
        print(f"FETCH page={page} rows={ROWS_PER_PAGE}")

        # 요청(백오프)
        backoff = 1.0
        for attempt in range(4):
            try:
                status, ctype, body = _http_get(url, timeout=20)
                if 200 <= status < 300:
                    break
                raise RuntimeError(f"HTTP {status}")
            except Exception as e:
                print(f"[Attempt {attempt+1}] page {page}: {e}")
                if attempt == 3:
                    raise
                time.sleep(backoff)
                backoff *= 2

        meta, items = _parse_xml_to_items(body)
        if meta["resultCode"] not in ("0", "00", "SUCCESS"):
            print(f"WARN resultCode={meta['resultCode']} msg={meta['resultMessage']}")
        if not items:
            print(f"page {page}: no items -> stop")
            break

        # 파일명/경로
        ts = now.strftime("%Y%m%dT%H%M%S")
        base_prefix = f"{PATH_PREFIX}/yyyy={yyyy}/mm={mm}/dd={dd}/hh={hh}"
        base_name   = f"localgov_040_003_p{page}_{ts}"

        # 1) XML 원본 저장
        key_xml = f"{base_prefix}/{base_name}.xml"
        s3.put_object(Bucket=S3_BUCKET, Key=key_xml, Body=body, ContentType="application/xml")
        saved["xml"].append(key_xml)

        # 2) JSON 요약 저장
        payload = {"meta": meta, "servList": items}
        key_json = f"{base_prefix}/{base_name}.json"
        s3.put_object(
            Bucket=S3_BUCKET, Key=key_json,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json"
        )
        saved["json"].append(key_json)

        total_processed += len(items)
        print(f"page {page}: saved xml/json, items={len(items)}")

        # 조기 종료(옵션): 오래된 데이터면 중단
        if cutoff:
            page_oldest = min((it.get("lastModYmd", "99999999") for it in items), default="99999999")
            if page_oldest < cutoff:
                print(f"page {page}: oldest {page_oldest} < cutoff {cutoff} -> stop")
                break

    print(f"processed items: {total_processed}, pages fetched: {len(saved['xml'])}")
    return {"ok": True, "bucket": S3_BUCKET, "saved": saved, "processed": total_processed}
