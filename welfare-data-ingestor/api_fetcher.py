# -*- coding: utf-8 -*-
import logging
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from config import API_CONSTANT_PARAMS

logger = logging.getLogger()

# ===== 헬퍼 함수 (이 모듈 내부에서만 사용) =====

def _http_get(url, timeout=20):
    """주어진 URL로 HTTP GET 요청을 보내고 응답을 반환합니다."""
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass # SSL 설정 실패 시 기본값 사용

    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    logger.info(f"API 요청: {url}")
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_xml_to_items(xml_bytes: bytes):
    """XML 바이트 데이터를 파싱하여 서비스 아이템 리스트를 반환합니다."""
    try:
        root = ET.fromstring(xml_bytes)
        result_code = root.findtext(".//resultCode") or ""

        if result_code not in ("0", "00", "SUCCESS"):
            logger.warning(f"API 비정상 응답: Code={result_code}, Msg={root.findtext('.//resultMessage')}")
            return [] # 비정상 응답 시 빈 리스트 반환

        items = []
        for serv_element in root.findall(".//servList"):
            item = {child.tag: (child.text or "").strip() for child in list(serv_element)}
            items.append(item)
        return items
    except ET.ParseError as e:
        logger.error(f"XML 파싱 오류: {e}\nXML Data (first 500 bytes): {xml_bytes[:500]}")
        return [] # 파싱 오류 시 빈 리스트 반환

# ===== API Fetcher 클래스 =====

class ApiFetcher:
    """외부 복지 서비스 API 연동을 담당하는 클래스"""

    def __init__(self, api_endpoint, service_key, rows_per_page):
        self.api_endpoint = api_endpoint
        self.service_key = service_key
        self.rows_per_page = rows_per_page

        # 기본 파라미터 설정 (고정값 + 설정값)
        self.base_params = API_CONSTANT_PARAMS.copy()
        self.base_params["serviceKey"] = self.service_key
        self.base_params["numOfRows"] = str(self.rows_per_page)

    def fetch_services_by_page(self, page_num, event_params=None):
        """특정 페이지 번호의 서비스 데이터를 API로부터 가져옵니다."""
        params = self.base_params.copy()
        params["pageNo"] = str(page_num)

        # 람다 실행 시 동적으로 받은 파라미터(event)가 있다면 덮어쓰기
        if event_params:
            for k, v in event_params.items():
                if v not in (None, ""):
                    params[k] = str(v)

        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{self.api_endpoint}?{query_string}"

            xml_body = _http_get(url)

            # XML 원본 로깅 (디버깅용, 필요시 활성화)
            # logger.debug(xml_body)

            return _parse_xml_to_items(xml_body)

        except urllib.error.URLError as e:
            logger.error(f"API 요청 실패 (Page: {page_num}): {e}")
            return [] # 네트워크 오류 시 빈 리스트 반환
        except Exception as e:
            logger.error(f"API 페이지 {page_num} 처리 중 예외 발생: {e}")
            return []
