# -*- coding: utf-8 -*-
import logging
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any

from app.fetcher.base_fetcher import BaseWelfareFetcher
from app.dto.common_dto import CommonServiceDTO
from app.config import API_CONSTANT_PARAMS # 지자체용 파라미터

logger = logging.getLogger()

# ===== 헬퍼 함수 (지자체 API - XML 처리용) =====
# 이 함수들은 LocalWelfareFetcher만 사용하므로 이 파일에 둡니다.

def _http_get(url: str, timeout: int = 20) -> bytes:
    """주어진 URL로 HTTP GET 요청을 보내고 응답을 bytes로 반환합니다."""
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass # SSL 설정 실패 시 기본값 사용

    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    logger.info(f"Local API 요청: {url}")
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_xml_to_items(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """XML 바이트 데이터를 파싱하여 서비스 아이템(dict) 리스트를 반환합니다."""
    try:
        root = ET.fromstring(xml_bytes)
        result_code = root.findtext(".//resultCode") or ""

        if result_code not in ("0", "00", "SUCCESS"):
            logger.warning(f"Local API 비정상 응답: Code={result_code}, Msg={root.findtext('.//resultMessage')}")
            return []

        items = []
        for serv_element in root.findall(".//servList"):
            item = {child.tag: (child.text or "").strip() for child in list(serv_element)}
            items.append(item)
        return items
    except ET.ParseError as e:
        logger.error(f"Local API XML 파싱 오류: {e}\nXML Data (first 500 bytes): {xml_bytes[:500]}")
        return []

# ===== 지자체 Fetcher 클래스 =====

class LocalWelfareFetcher(BaseWelfareFetcher):
    """지자체 복지 서비스(XML) API 연동을 담당하는 Fetcher"""

    def __init__(self, api_endpoint: str, service_key: str, rows_per_page: int):
        """
        지자체 API Fetcher를 초기화합니다.

        :param api_endpoint: 지자체 API 엔드포인트 URL
        :param service_key: 지자체 API 서비스 키
        :param rows_per_page: 페이지 당 요청할 행 수
        """
        self.api_endpoint = api_endpoint
        self.service_key = service_key
        self.rows_per_page = rows_per_page

        # 기본 파라미터 설정 (지자체 API 고정값 사용)
        self.base_params = API_CONSTANT_PARAMS.copy()
        self.base_params["serviceKey"] = self.service_key
        self.base_params["numOfRows"] = str(self.rows_per_page)
        logger.info(f"LocalWelfareFetcher 초기화 완료 (Endpoint: {api_endpoint})")

    def _map_to_dto(self, item: Dict[str, Any]) -> CommonServiceDTO:
        """XML 파싱 결과(dict)를 CommonServiceDTO로 변환(어댑터 로직)"""

        # DTO 변환에 필요한 헬퍼 함수들
        def _format_date(ymd_string: Optional[str]) -> Optional[str]:
            """'YYYYMMDD' -> 'YYYY-MM-DD'"""
            if ymd_string and len(ymd_string) == 8:
                try:
                    return f"{ymd_string[:4]}-{ymd_string[4:6]}-{ymd_string[6:]}"
                except Exception:
                    return None
            return None

        def _split_text(text: Optional[str]) -> List[str]:
            """'A,B,C' -> ['A', 'B', 'C']"""
            if not text:
                return []
            return list(filter(None, text.split(',')))

        # CommonServiceDTO 객체 생성
        return CommonServiceDTO(
            service_id=item.get('servId'),
            service_name=item.get('servNm'),
            service_summary=item.get('servDgst'),
            detail_link=item.get('servDtlLink'),

            # 지자체 API 필드 매핑
            department_name=item.get('bizChrDeptNm'), # 소관부처
            province=item.get('ctpvNm'),             # 시도
            city_district=item.get('sggNm'),         # 시군구

            # 배열 필드 매핑
            target_audience=_split_text(item.get('trgterIndvdlNmArray')),
            life_cycle=_split_text(item.get('lifeNmArray')),
            interest_theme=_split_text(item.get('intrsThemaNmArray')),

            # 기타 필드
            support_cycle=item.get('sprtCycNm'),
            support_type=item.get('srvPvsnNm'),
            application_method=item.get('aplyMtdNm'),

            # 날짜 변환
            last_modified_date=_format_date(item.get('lastModYmd'))
        )

    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[CommonServiceDTO]:
        """
        지자체 API의 특정 페이지를 조회하여 CommonServiceDTO 리스트로 반환합니다.
        """
        params = self.base_params.copy()
        params["pageNo"] = str(page_num)

        # [수정] 람다 event 파라미터 중 API가 아는 것만 선별하여 전달
        if event_params:
            # 지자체 API가 동적으로 받을 수 있는 파라미터 목록
            known_params = {
                "trgterIndvdlArray", # 대상 (기본값 040)
                "srchKeyCode",       # 검색조건 (기본값 003)
                "arrgOrd",           # 정렬 (기본값 001)
                "searchWrd",         # 검색어
                "lifeArray",         # 생애주기
                "intrsThemaArray",   # 관심주제
            }

            for k, v in event_params.items():
                if k in known_params and v not in (None, ""):
                    logger.info(f"Event 파라미터 적용 (Local): {k}={v}")
                    params[k] = str(v)

        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{self.api_endpoint}?{query_string}"

            # 1. API 호출 (Bytes)
            xml_body = _http_get(url)

            # 2. XML 파싱 (List[dict])
            raw_items = _parse_xml_to_items(xml_body)
            if not raw_items:
                return []

            # 3. DTO로 변환 (List[CommonServiceDTO])
            dto_list = []
            for item in raw_items:
                if item.get('servId'): # 서비스 ID가 있는 유효한 항목만 DTO로 변환
                    dto_list.append(self._map_to_dto(item))

            logger.info(f"Local API 페이지 {page_num} 조회 완료 (DTO {len(dto_list)}개 변환)")
            return dto_list

        except urllib.error.URLError as e:
            logger.error(f"Local API 요청 실패 (Page: {page_num}): {e}")
            return [] # 네트워크 오류 시 빈 리스트 반환
        except Exception as e:
            logger.error(f"Local API 페이지 {page_num} 처리 중 예외 발생: {e}", exc_info=True)
            return []
