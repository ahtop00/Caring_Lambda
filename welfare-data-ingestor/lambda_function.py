# -*- coding: utf-8 -*-
import os
import json
import time
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import ssl
import logging

import boto3
import psycopg2
from botocore.config import Config
from botocore.exceptions import ClientError

# ===== 로거 설정 =====
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ===== 환경 변수 로드 =====
try:
    # API Fetcher용 변수
    API_ENDPOINT = os.environ["API_ENDPOINT"]
    SERVICE_KEY  = os.environ["SERVICE_KEY"]
    ROWS_PER_PAGE = int(os.environ.get("ROWS_PER_PAGE", "100"))
    PAGE_LIMIT    = int(os.environ.get("PAGE_LIMIT", "100")) # 초기 적재를 위해 기본값을 100으로 설정

    # <<< 1. 시작 페이지 번호를 위한 환경 변수 추가 >>>
    START_PAGE = int(os.environ.get("START_PAGE", "1"))

    # Vector DB Ingestor용 변수
    DB_HOST = os.environ['DB_HOST']
    DB_NAME = os.environ['DB_NAME']
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
except KeyError as e:
    logger.error(f"FATAL: 필수 환경 변수가 누락되었습니다: {e}")
    raise e

# ===== AWS 클라이언트 초기화 =====
bedrock_runtime = boto3.client(service_name='bedrock-runtime')


# ===== 헬퍼 함수 (Helper Functions) =====

def get_embedding(text, model_id='amazon.titan-embed-text-v2:0'):
    """주어진 텍스트를 Amazon Bedrock Titan v2 모델을 이용해 벡터로 변환합니다."""
    body = json.dumps({"inputText": text})
    try:
        response = bedrock_runtime.invoke_model(
            body=body, modelId=model_id,
            accept='application/json', contentType='application/json'
        )
        response_body = json.loads(response.get('body').read())
        return response_body.get('embedding')
    except ClientError as e:
        logger.error(f"Bedrock API 호출 중 오류 발생: {e}")
        raise e

def _http_get(url, timeout=20):
    """주어진 URL로 HTTP GET 요청을 보내고 응답을 반환합니다."""
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass

    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_xml_to_items(xml_bytes: bytes):
    """XML 바이트 데이터를 파싱하여 메타 정보와 서비스 아이템 리스트를 반환합니다."""
    root = ET.fromstring(xml_bytes)
    result_code = root.findtext(".//resultCode") or ""
    if result_code not in ("0", "00", "SUCCESS"):
        logger.warning(f"API 비정상 응답: Code={result_code}, Msg={root.findtext('.//resultMessage')}")

    items = []
    for serv_element in root.findall(".//servList"):
        item = {child.tag: (child.text or "").strip() for child in list(serv_element)}
        items.append(item)
    return items


# ===== 메인 핸들러 (Main Handler) =====

def handler(event, context):
    logger.info(f"## 통합 Lambda 실행 시작 (시작 페이지: {START_PAGE}, 페이지 제한: {PAGE_LIMIT}) ##")

    total_inserted_count = 0
    conn = None

    try:
        # 1. 데이터베이스 연결
        logger.info(f"데이터베이스 연결 시도... (Host: {DB_HOST})")
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER,
            password=DB_PASSWORD, connect_timeout=10
        )
        cur = conn.cursor()
        logger.info("데이터베이스 연결 성공.")

        # <<< 2. for 루프의 시작점을 START_PAGE로 변경 >>>
        end_page = START_PAGE + PAGE_LIMIT
        for page in range(START_PAGE, end_page):
            logger.info(f"--- API 페이지 {page}/{end_page - 1} 조회 시작 ---")

            params = { "serviceKey": SERVICE_KEY, "pageNo": str(page), "numOfRows": str(ROWS_PER_PAGE), "trgterIndvdlArray": "040", "srchKeyCode": "003", "arrgOrd": "001" }
            if event:
                for k, v in event.items():
                    if v not in (None, ""): params[k] = str(v)
            query_string = urllib.parse.urlencode(params)
            url = f"{API_ENDPOINT}?{query_string}"
            body = _http_get(url)
            logger.info(body)

            services_from_api = _parse_xml_to_items(body)
            if not services_from_api:
                logger.info(f"페이지 {page}에서 더 이상 조회된 서비스가 없어 전체 작업을 중단합니다.")
                break

            logger.info(f"페이지 {page}에서 {len(services_from_api)}개의 서비스를 API로부터 수신했습니다.")

            ids_from_api = [s.get('servId') for s in services_from_api if s.get('servId')]

            cur.execute("SELECT id FROM welfare_services WHERE id = ANY(%s)", (ids_from_api,))
            existing_ids = {row[0] for row in cur.fetchall()}
            logger.info(f"DB 조회 결과, {len(existing_ids)}개의 서비스가 이미 존재합니다.")

            new_services = [s for s in services_from_api if s.get('servId') not in existing_ids]

            if not new_services:
                logger.info(f"페이지 {page}에는 신규 서비스가 없습니다. 다음 페이지로 넘어갑니다.")
            else:
                logger.info(f"페이지 {page}에서 {len(new_services)}개의 신규 서비스를 발견했습니다. 임베딩 및 DB 저장을 시작합니다.")

                page_inserted_count = 0
                for i, service in enumerate(new_services, 1):
                    service_id = service.get('servId')

                    text_to_embed = (
                        f"이 복지 서비스는 {service.get('ctpvNm') or ''} {service.get('sggNm') or ''} 지역의 {service.get('trgterIndvdlNmArray') or '정보 없음'}를 대상으로 합니다. "
                        f"지원 주기는 {service.get('sprtCycNm') or '정보 없음'}이며, {service.get('srvPvsnNm') or '정보 없음'} 형태로 제공됩니다. "
                        f"신청은 {service.get('aplyMtdNm') or '정보 없음'} 방식으로 할 수 있습니다. "
                        f"서비스명은 '{service.get('servNm', '')}'이고, 주요 내용은 다음과 같습니다: {service.get('servDgst', '')}"
                    )
                    embedding = get_embedding(text_to_embed)

                    last_mod_ymd = service.get('lastModYmd')
                    last_modified_date = f"{last_mod_ymd[:4]}-{last_mod_ymd[4:6]}-{last_mod_ymd[6:]}" if last_mod_ymd and len(last_mod_ymd) == 8 else None

                    params_for_db = (
                        service_id, service.get('servNm'), service.get('servDgst'), embedding,
                        service.get('ctpvNm'), service.get('sggNm'), service.get('bizChrDeptNm'),
                        list(filter(None, service.get('trgterIndvdlNmArray', '').split(','))),
                        list(filter(None, service.get('lifeNmArray', '').split(','))),
                        list(filter(None, service.get('intrsThemaNmArray', '').split(','))),
                        service.get('sprtCycNm'), service.get('srvPvsnNm'), service.get('aplyMtdNm'),
                        last_modified_date, service.get('servDtlLink')
                    )

                    sql_insert = """
                        INSERT INTO welfare_services (id, service_name, service_summary, embedding, province, city_district, department_name, target_audience, life_cycle, interest_theme, support_cycle, support_type, application_method, last_modified_date, detail_link)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cur.execute(sql_insert, params_for_db)
                    page_inserted_count += 1
                    time.sleep(0.1)

                if page_inserted_count > 0:
                    conn.commit()
                    logger.info(f"페이지 {page}의 신규 서비스 {page_inserted_count}개 항목을 DB에 커밋했습니다.")
                total_inserted_count += page_inserted_count

            logger.info("다음 페이지 조회를 위해 1초 대기합니다.")
            time.sleep(1)

        logger.info(f"총 {total_inserted_count}개의 신규 레코드를 성공적으로 추가했습니다.")
        return {'statusCode': 200, 'body': json.dumps(f"성공적으로 총 {total_inserted_count}개의 신규 서비스를 처리했습니다.")}

    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        if conn: conn.rollback()
        raise e

    finally:
        if conn:
            cur.close()
            conn.close()
            logger.info("데이터베이스 연결을 종료했습니다.")
        logger.info("## 통합 Lambda 실행 종료 ##")
