# chatbot/util/response_builder.py
import re
from typing import List, Optional, Tuple

def extract_locations(query: str) -> Optional[List[str]]:
    """쿼리에서 지역명을 추출합니다."""
    pattern = re.compile(r"(\S+[시군구도])(?:은|는|이|가|을|를|도|에|에서|의)?")
    matches = pattern.findall(query)
    return list(set(matches)) if matches else None

def normalize_results(results: List, result_type: str) -> List[Tuple[float, tuple]]:
    """DB 검색 결과를 표준 튜플 리스트로 변환합니다."""
    normalized_list = []

    if result_type == "EMPLOYMENT":
        for row in results:
            score, job_title, company_name, job_description, detail_link, location = row
            name = f"{company_name} - {job_title}"
            summary = job_description or f"{company_name}의 {job_title} 채용"
            url = detail_link or "상세 링크 정보 없음"

            province = location or "전국"
            city_district = ""
            if location and ' ' in location:
                parts = location.split(' ', 2)
                province = parts[0]
                city_district = parts[1] if len(parts) > 1 else ""

            normalized_list.append((score, (name, summary, url, province, city_district)))

    else: # "WELFARE"
        for row in results:
            score = row[0]
            data_tuple = row[1:]
            normalized_list.append((score, data_tuple))

    return normalized_list

def rerank_results(results: List, locations: Optional[List[str]]) -> List:
    """지역 기반 재순위화 로직"""
    if not locations or not results:
        return results[:3]

    ranked = []
    for row in results:
        service_name, summary, _, province, city_district = row
        score = 0
        for loc in locations:
            if loc in service_name or loc in summary or loc == province or loc == city_district:
                score += 10
        ranked.append({'score': score, 'data': row})

    sorted_results = sorted(ranked, key=lambda x: x['score'], reverse=True)
    return [item['data'] for item in sorted_results[:3]]

def format_context_string(results: List) -> str:
    """LLM 프롬프트용 컨텍스트 문자열 생성"""
    context_items = []
    for i, (name, summary, url, prov, city) in enumerate(results, 1):
        region = f"{prov} {city}".strip() or "전국"
        context_items.append(
            f"문서 {i}:\n서비스명: {name}\n요약: {summary}\n지역: {region}\n링크: {url}\n"
        )
    return "\n".join(context_items)
