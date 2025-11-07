# data_processor.py
import json
import re
from typing import Any, Dict, List, Optional

def parse_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """이벤트 Body를 파싱하고 필수 값을 추출합니다."""
    body = json.loads(event.get('body', '{}'))
    user_info = body.get('query1', '제공된 정보 없음')
    user_chat = body.get('query2')

    if not user_chat:
        raise ValueError("query2가 누락되었습니다.")

    return {"user_info": user_info, "user_chat": user_chat}

# LLM 의도 분류 응답 파서
def parse_intent(llm_response: str) -> str:
    """
    LLM의 분류 응답 문자열을 파싱하여 'WELFARE' 또는 'EMPLOYMENT'를 반환합니다.
    """
    if "EMPLOYMENT" in llm_response.upper():
        return "EMPLOYMENT"
    # 그 외 모든 경우(WELFARE, 파싱 실패, 오류 등) '복지'를 기본값으로 합니다.
    return "WELFARE"

def extract_locations(query: str) -> Optional[List[str]]:
    """쿼리에서 지역명을 추출합니다."""
    pattern = re.compile(r"(\S+[시군구도])(?:은|는|이|가|을|를|도|에|에서|의)?")
    matches = pattern.findall(query)
    return list(set(matches)) if matches else None

# DB 결과 정규화 함수
def normalize_results(results: List, result_type: str) -> List:
    """
    서로 다른 DB 검색 결과를 (name, summary, url, prov, city) 표준 튜플 리스트로 정규화합니다.
    이 작업을 통해 rerank_results와 format_context_string 함수를 수정할 필요가 없어집니다.
    """
    normalized_list = []

    if result_type == "EMPLOYMENT":
        # 'employment_jobs' 테이블의 예상 컬럼 순서:
        # (job_title, company_name, job_description, detail_link, location)
        for row in results:
            job_title, company_name, job_description, detail_link, location = row

            # (name, summary, url, prov, city) 튜플로 변환
            name = f"{company_name} - {job_title}"
            summary = job_description or f"{company_name}의 {job_title} 채용"
            url = detail_link or "상세 링크 정보 없음"

            # location(단일 문자열)을 prov, city로 분해 (간단한 방식)
            province = location or "전국"
            city_district = ""
            if location and ' ' in location:
                # '서울 강남구' -> ['서울', '강남구']
                # '서울' -> ['서울']
                parts = location.split(' ', 2) # 최대 2개로 분리
                province = parts[0]
                city_district = parts[1] if len(parts) > 1 else ""

            normalized_list.append((name, summary, url, province, city_district))
        return normalized_list

    else: # "WELFARE"
        # 'welfare_services' 테이블의 컬럼 순서는 이미 표준과 일치합니다.
        # (service_name, service_summary, detail_link, province, city_district)
        # 따라서 그대로 반환합니다.
        return results

def rerank_results(results: List, locations: Optional[List[str]]) -> List:
    """
    검색 결과를 지역명 관련도에 따라 재순위화하고 상위 3개를 반환합니다.
    normalize_results() 덕분에 이 함수는 '복지'와 '고용' 모두 동일하게 처리할 수 있습니다.
    """
    if not locations or not results:
        return results[:3]

    ranked = []
    # 'row'는 (name, summary, url, province, city_district) 튜플입니다.
    for row in results:
        service_name, summary, _, province, city_district = row
        score = 0
        for loc in locations:
            # service_name이 '회사명 - 직무'이든 '서비스명'이든 상관없이 검색됩니다.
            if loc in service_name or loc in summary or loc == province or loc == city_district:
                score += 10
        ranked.append({'score': score, 'data': row})

    sorted_results = sorted(ranked, key=lambda x: x['score'], reverse=True)
    return [item['data'] for item in sorted_results[:3]]

def format_context_string(results: List) -> str:
    """
    LLM에 전달할 컨텍스트 문자열을 포맷팅합니다.
    normalize_results() 덕분에 이 함수도 '복지'와 '고용' 모두 동일하게 처리할 수 있습니다.
    """
    context_items = []
    # results의 각 항목은 (name, summary, url, prov, city) 튜플입니다.
    for i, (name, summary, url, prov, city) in enumerate(results, 1):
        region = f"{prov} {city}".strip() or "전국"
        context_items.append(
            # [최적화 제안] 토큰을 아끼려면 summary를 잘라낼 수 있습니다. (예: {summary[:500]})
            f"문서 {i}:\n서비스명: {name}\n요약: {summary}\n지역: {region}\n링크: {url}\n"
        )
    return "\n".join(context_items)

def build_response(status_code: int, body: Dict) -> Dict[str, Any]:
    """
    API Gateway에 반환할 표준 응답을 생성합니다. (API 인터페이스 유지)
    """
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, ensure_ascii=False)
    }
