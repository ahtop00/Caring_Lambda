# -*- coding: utf-8 -*-
import logging
import json
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # [수정] XML 파서를 임포트
from typing import List, Optional, Dict, Any

from fetcher.base_fetcher import BaseWelfareFetcher
from app.dto.common_dto import CommonServiceDTO
from app.config import CENTRAL_API_CONSTANT_PARAMS, CENTRAL_API_KEY


logger = logging.getLogger()

# ===== 헬퍼 함수 (XML 처리용) =====

def _http_get_xml(url: str, timeout: int = 20) -> bytes:
    """[수정] XML을 받기 위한 HTTP GET 요청"""
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass

    # [수정] Accept 헤더를 application/xml로 변경
    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    logger.info(f"Central API (XML) 요청: {url}")
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_xml_to_items_central(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """[신규] 중앙부처 API의 XML을 파싱하는 함수"""
    try:
        root = ET.fromstring(xml_bytes)

        # 중앙부처 API는 'wantedList' 요소로 감싸져 있음
        wanted_list_element = root.find(".//wantedList")
        if wanted_list_element is None:
            # 'wantedList'가 없는 경우, 오류 응답인지 확인
            result_code = root.findtext(".//resultCode")
            if result_code is not None and result_code not in ("00", "0"): # 00 또는 0 (지자체 호환)
                 logger.warning(f"Central API (XML) 비정상 응답: Code={result_code}, Msg={root.findtext('.//resultMessage')}")
            else:
                 logger.warning("Central API (XML) 응답에 'wantedList' 요소가 없습니다.")
            return []

        # 'wantedList' 내부의 resultCode 확인 (성공 코드가 '00'이어야 함)
        result_code = wanted_list_element.findtext(".//resultCode")
        if result_code != "00":
            logger.warning(f"Central API (XML) 비정상 응답: Code={result_code}, Msg={wanted_list_element.findtext('.//resultMessage')}")
            return []

        items = []
        # 'wantedList' 내부의 'servList'들을 찾음
        for serv_element in wanted_list_element.findall(".//servList"):
            item = {child.tag: (child.text or "").strip() for child in list(serv_element)}
            items.append(item)
        return items

    except ET.ParseError as e:
        logger.error(f"Central API XML 파싱 오류: {e}\nXML Data (first 500 bytes): {xml_bytes[:500]}")
        return []
    except Exception as e:
        logger.error(f"Central API XML 처리 중 알 수 없는 오류: {e}")
        return []

# ===== 중앙부처 Fetcher 클래스 =====

class CentralWelfareFetcher(BaseWelfareFetcher):
    """중앙부처 복지 서비스(XML) API 연동을 담당하는 Fetcher"""

    def __init__(self, api_endpoint: str, service_key: str, rows_per_page: int):
        """
        중앙부처 API Fetcher를 초기화합니다.
        (이 로직은 변경 없음)
        """
        self.api_endpoint = api_endpoint
        self.service_key = service_key
        self.rows_per_page = rows_per_page

        # 기본 파라미터 설정 (중앙부처 API 고정값 사용)
        self.base_params = CENTRAL_API_CONSTANT_PARAMS.copy()
        self.base_params["serviceKey"] = self.service_key
        self.base_params["numOfRows"] = str(self.rows_per_page)
        # API 명세서(이미지)에서 필수값(callTp) 확인
        self.base_params["callTp"] = "L" # 'L': 목록조회

        logger.info(f"CentralWelfareFetcher 초기화 완료 (Endpoint: {api_endpoint})")

    def _map_to_dto(self, item: Dict[str, Any]) -> CommonServiceDTO:
        """
        파싱된 딕셔너리(item)를 CommonServiceDTO로 변환합니다.
        (이 로직은 변경 없음)
        """
        def _format_datetime(dt_string: Optional[str]) -> Optional[str]:
            """'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD'"""
            if dt_string and ' ' in dt_string:
                return dt_string.split(' ')[0]
            elif dt_string and len(dt_string) == 8: # YYYYMMDD 형식일 경우
                 return f"{dt_string[:4]}-{dt_string[4:6]}-{dt_string[6:]}"
            return dt_string # 형식이 다르거나 날짜만 있을 경우 그대로 반환

        def _split_text(text: Optional[str]) -> List[str]:
            """'A,B,C' -> ['A', 'B', 'C']"""
            if not text:
                return []
            return list(filter(None, text.split(',')))

        def _map_application_method(onap_yn: Optional[str]) -> str:
            """'Y' -> '온라인 신청', 'N' -> '방문/전화 신청', else '정보 없음'"""
            if onap_yn == 'Y':
                return '온라인 신청'
            if onap_yn == 'N':
                return '방문/전화 신청' # (API 명세에 따라 '방문', '전화' 등 구체화)
            return '정보 없음'

        return CommonServiceDTO(
            service_id=item.get('servId'),
            service_name=item.get('servNm'),
            service_summary=item.get('servDgst'),
            detail_link=item.get('servDtlLink'),
            department_name=item.get('jurMnofNm') or item.get('jurOrgNm'),
            province=None,
            city_district=None,
            target_audience=_split_text(item.get('trgterIndvdlArray')),
            life_cycle=_split_text(item.get('lifeArray')),
            interest_theme=_split_text(item.get('intrsThemaNmArray')),
            support_cycle=item.get('sprtCycNm'),
            support_type=item.get('srvPvsnNm'),
            application_method=_map_application_method(item.get('onapPsbltYn')),
            last_modified_date=_format_datetime(item.get('svcfrstRegTs'))
        )

    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[CommonServiceDTO]:
        """
        중앙부처 API의 XML을 조회하여 DTO 리스트로 반환합니다.
        """
        params = self.base_params.copy()
        params["pageNo"] = str(page_num)

        if event_params:
            known_params = {
                "searchWrd", "lifeArray", "trgterIndvdlArray",
                "intrsThemaArray", "age", "onapPsbltYn", "orderBy",
                "srchKeyCode"
            }
            for k, v in event_params.items():
                if k in known_params and v not in (None, ""):
                    logger.info(f"Event 파라미터 적용 (Central): {k}={v}")
                    params[k] = str(v)

        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{self.api_endpoint}?{query_string}"

            xml_body = _http_get_xml(url)

            raw_items = _parse_xml_to_items_central(xml_body)
            if not raw_items:
                return []

            dto_list = []
            for item in raw_items:
                if item.get('servId'): # 서비스 ID가 있는 유효한 항목만 DTO로 변환
                    dto_list.append(self._map_to_dto(item))

            logger.info(f"Central API (XML) 페이지 {page_num} 조회 완료 (DTO {len(dto_list)}개 변환)")
            return dto_list

        except urllib.error.URLError as e:
            logger.error(f"Central API 요청 실패 (Page: {page_num}): {e}")
            return [] # 네트워크 오류 시 빈 리스트 반환
        except Exception as e:
            logger.error(f"Central API 페이지 {page_num} 처리 중 예외 발생: {e}", exc_info=True)
            return []
