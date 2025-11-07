# -*- coding: utf-8 -*-
import logging
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any

from app.fetcher.base_fetcher import BaseWelfareFetcher
from app.dto.employment_dto import JobOpeningDTO # 신규 DTO 임포트

logger = logging.getLogger()

# ... ( _http_get, _parse_employment_xml 헬퍼 함수는 기존과 동일 ... )
def _http_get(url: str, timeout: int = 20) -> bytes:
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    logger.info(f"Employment API 요청: {url}")
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()

def _parse_employment_xml(xml_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(xml_bytes)
        result_code = root.findtext(".//header/resultCode") or ""
        if result_code != "0000":
            logger.warning(f"Employment API 비정상 응답: Code={result_code}, Msg={root.findtext('.//header/resultMsg')}")
            return []
        items = []
        for item_element in root.findall(".//body/items/item"):
            item = {child.tag: (child.text or "").strip() for child in list(item_element)}
            items.append(item)
        return items
    except ET.ParseError as e:
        logger.error(f"Employment API XML 파싱 오류: {e}\nXML Data (first 500 bytes): {xml_bytes[:500]}")
        return []

class EmploymentFetcher(BaseWelfareFetcher):
    """
    '구인 정보' API 연동을 담당하는 Fetcher (수정)
    """

    def __init__(self, api_endpoint: str, service_key: str, rows_per_page: int):
        self.api_endpoint = api_endpoint
        self.service_key = service_key
        self.rows_per_page = rows_per_page
        logger.info("EmploymentFetcher 초기화 완료.")

    def _map_to_dto(self, item: Dict[str, Any]) -> JobOpeningDTO:
        """
        [수정]
        API 원본 데이터(dict)를 JobOpeningDTO로 변환 (job_id 제거, termDate 추가)
        """

        # YYYYMMDD -> YYYY-MM-DD
        reg_dt = item.get('regDt')
        if reg_dt and len(reg_dt) == 8:
            last_mod_date = f"{reg_dt[:4]}-{reg_dt[4:6]}-{reg_dt[6:]}"
        else:
            last_mod_date = None

        # 스킬 파싱 (예: "바리스타 2급/")
        skills = [s.strip() for s in item.get('reqLicens', '').split('/') if s.strip()]

        return JobOpeningDTO(
            # [수정] job_id 제거
            company_name=item.get('busplaName'),
            job_title=item.get('jobNm'),
            job_description=f"{item.get('jobNm')} 직무 채용", # 임시 설명
            detail_link=item.get('detailLink'), # [수정 필요]
            job_type=item.get('empType'),
            salary=item.get('salary'),
            salary_type=item.get('salaryType'),
            location=item.get('compAddr'),
            required_skills=skills,
            required_career=item.get('reqCareer'),
            required_education=item.get('reqEduc'),
            last_modified_date=last_mod_date,
            term_date_str=item.get('termDate') # [신규] "2025-11-04~2025-11-13"
        )

    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[JobOpeningDTO]:
        # (기존과 동일하게 유지)
        params = {
            "serviceKey": self.service_key,
            "pageNo": str(page_num),
            "numOfRows": str(self.rows_per_page)
        }
        if event_params:
            for k, v in event_params.items():
                if k not in ("source", "serviceKey", "pageNo", "numOfRows") and v:
                    params[k] = str(v)
        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{self.api_endpoint}?{query_string}"
            xml_bytes = _http_get(url)
            raw_items = _parse_employment_xml(xml_bytes)
            if not raw_items:
                return []
            dto_list = [self._map_to_dto(item) for item in raw_items]
            logger.info(f"Employment API 페이지 {page_num} 조회 완료 (DTO {len(dto_list)}개 변환)")
            return dto_list
        except Exception as e:
            logger.error(f"Employment API 페이지 {page_num} 처리 중 예외 발생: {e}", exc_info=True)
            return []
