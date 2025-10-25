# -*- coding: utf-8 -*-
import logging
import json
import ssl
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any

from fetchers.base_fetcher import BaseWelfareFetcher
from common_dto import CommonServiceDTO
from config import CENTRAL_API_CONSTANT_PARAMS, CENTRAL_API_KEY


logger = logging.getLogger()

# ===== 헬퍼 함수 (중앙부처 API - JSON 처리용) =====

def _http_get_json(url: str, timeout: int = 20) -> bytes:
    """주어진 URL로 HTTP GET 요청을 보내고 응답을 bytes로 반환합니다."""
    # Local Fetcher와 동일한 SSL 컨텍스트 사용
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass

    # Accept 헤더를 application/json으로 변경
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    logger.info(f"Central API 요청: {url}")
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_json_to_items(json_bytes: bytes) -> List[Dict[str, Any]]:
    """JSON 바이트 데이터를 파싱하여 서비스 아이템(dict) 리스트를 반환합니다."""
    try:
        data = json.loads(json_bytes.decode('utf-8'))

        # 응답 구조(wantedList)에 따라 파싱
        wanted_list = data.get('wantedList', {})
        if not wanted_list:
            logger.warning("Central API 응답에 'wantedList' 키가 없습니다.")
            return []

        result_code = wanted_list.get('resultCode')
        # API 문서상 성공 코드가 '00'일 수 있습니다. (지자체는 '00' 또는 '0')
        if result_code != "00":
            logger.warning(f"Central API 비정상 응답: Code={result_code}, Msg={wanted_list.get('resultMessage')}")
            return []

        return wanted_list.get('servList', [])

    except json.JSONDecodeError as e:
        logger.error(f"Central API JSON 파싱 오류: {e}\nJSON Data (first 500 bytes): {json_bytes[:500]}")
        return []
    except Exception as e:
        logger.error(f"Central API JSON 처리 중 알 수 없는 오류: {e}")
        return []

# ===== 중앙부처 Fetcher 클래스 =====

class CentralWelfareFetcher(BaseWelfareFetcher):
    """중앙부처 복지 서비스(JSON) API 연동을 담당하는 Fetcher"""

    def __init__(self, api_endpoint: str, service_key: str, rows_per_page: int):
        """
        중앙부처 API Fetcher를 초기화합니다.

        :param api_endpoint: 중앙부처 API 엔드포인트 URL
        :param service_key: 중앙부처 API 서비스 키
        :param rows_per_page: 페이지 당 요청할 행 수
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
        """JSON API 결과(dict)를 CommonServiceDTO로 변환(어댑터 로직)"""

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

            # 중앙부처 API 필드 매핑
            # jurMnofNm(소관부처명), jurOrgNm(소관조직명) 중 더 적절한 값 사용
            department_name=item.get('jurMnofNm') or item.get('jurOrgNm'),
            province=None,         # 중앙부처는 지역 정보 없음
            city_district=None,

            # 배열 필드 매핑
            target_audience=_split_text(item.get('trgterIndvdlArray')),
            life_cycle=_split_text(item.get('lifeArray')),
            interest_theme=_split_text(item.get('intrsThemaArray')),

            # 기타 필드
            support_cycle=item.get('sprtCycNm'),
            support_type=item.get('srvPvsnNm'),
            # API 응답(onapPsbltYn)을 기반으로 변환
            application_method=_map_application_method(item.get('onapPsbltYn')),

            # 날짜 변환 (svcfrstRegTs: 서비스등록일)
            last_modified_date=_format_datetime(item.get('svcfrstRegTs'))
        )

    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[CommonServiceDTO]:
        """
        중앙부처 API의 특정 페이지를 조회하여 CommonServiceDTO 리스트로 반환합니다.
        """
        params = self.base_params.copy()
        params["pageNo"] = str(page_num)

        if event_params:
            known_params = {
                "searchWrd", "lifeArray", "trgterIndvdlArray",
                "intrsThemaArray", "age", "onapPsbltYn", "orderBy",
                "srchKeyCode" # (event에서 기본값 '003'을 덮어쓸 수 있도록 허용)
            }

            for k, v in event_params.items():
                if k in known_params and v not in (None, ""):
                    logger.info(f"Event 파라미터 적용 (Central): {k}={v}")
                    params[k] = str(v)

        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{self.api_endpoint}?{query_string}"

            # 1. API 호출 (Bytes)
            json_body = _http_get_json(url)

            # 2. JSON 파싱 (List[dict])
            raw_items = _parse_json_to_items(json_body)
            if not raw_items:
                return []

            # 3. DTO로 변환 (List[CommonServiceDTO])
            dto_list = []
            for item in raw_items:
                if item.get('servId'): # 서비스 ID가 있는 유효한 항목만 DTO로 변환
                    dto_list.append(self._map_to_dto(item))

            logger.info(f"Central API 페이지 {page_num} 조회 완료 (DTO {len(dto_list)}개 변환)")
            return dto_list

        except urllib.error.URLError as e:
            logger.error(f"Central API 요청 실패 (Page: {page_num}): {e}")
            return [] # 네트워크 오류 시 빈 리스트 반환
        except Exception as e:
            logger.error(f"Central API 페이지 {page_num} 처리 중 예외 발생: {e}", exc_info=True)
            return []
