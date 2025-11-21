# data_processor.py
import json
import re
from typing import Any, Dict, List, Optional

def parse_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """이벤트 Body를 파싱하고 필수 값을 추출합니다. (검색용)"""
    body = json.loads(event.get('body', '{}'))
    user_info = body.get('query1', '제공된 정보 없음')
    user_chat = body.get('query2')

    if not user_chat:
        raise ValueError("query2가 누락되었습니다.")

    return {"user_info": user_info, "user_chat": user_chat}

def parse_reframing_body(event: Dict[str, Any]) -> str:
    """리프레이밍 요청 Body에서 사용자 입력을 추출합니다."""
    try:
        body = json.loads(event.get('body', '{}'))
        # 프론트엔드에서 보낼 JSON 키 이름을 'user_input'으로 가정
        user_input = body.get('user_input')

        if not user_input:
            raise ValueError("요청 Body에 'user_input' 값이 누락되었습니다.")

        return user_input
    except json.JSONDecodeError:
        raise ValueError("잘못된 JSON 형식입니다.")

def extract_locations(query: str) -> Optional[List[str]]:
    """쿼리에서 지역명을 추출합니다."""
    pattern = re.compile(r"(\S+[시군구도])(?:은|는|이|가|을|를|도|에|에서|의)?")
    matches = pattern.findall(query)
    return list(set(matches)) if matches else None

# DB 결과 정규화 함수 (score를 입력받고, score를 반환)
def normalize_results(results: List, result_type: str) -> List[tuple[float, tuple]]:
    """
    서로 다른 DB 검색 결과를 (score, (name, summary, url, prov, city)) 표준 튜플 리스트로 정규화합니다.
    """
    normalized_list = []

    if result_type == "EMPLOYMENT":
        # 'employment_jobs' 테이블 컬럼 순서 (database.py에서 수정됨):
        # (score, job_title, company_name, job_description, detail_link, location)
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

            # (score, (name, ...)) 튜플로 변환
            normalized_list.append((score, (name, summary, url, province, city_district)))
        return normalized_list

    else: # "WELFARE"
        # 'welfare_services' 테이블 컬럼 순서 (database.py에서 수정됨):
        # (score, service_name, service_summary, detail_link, province, city_district)
        for row in results:
            score = row[0]
            # (name, ...) 튜플 생성 (row[1]부터 끝까지)
            data_tuple = row[1:]
            normalized_list.append((score, data_tuple))
        return normalized_list

def rerank_results(results: List, locations: Optional[List[str]]) -> List:
    """
    (name, summary, ...) 튜플 리스트를 입력받아 지역명으로 재순위화합니다.
    lambda_function.py에서 이미 score로 상위 3개가 필터링된 리스트가 넘어옵니다.
    """
    if not locations or not results:
        # 지역 정보가 없으면, 이미 score로 정렬된 상위 3개를 그대로 반환
        return results[:3]

    ranked = []
    # 'row'는 (name, summary, url, province, city_district) 튜플입니다.
    for row in results:
        service_name, summary, _, province, city_district = row
        score = 0 # 지역 점수
        for loc in locations:
            # service_name이 '회사명 - 직무'이든 '서비스명'이든 상관없이 검색됩니다.
            if loc in service_name or loc in summary or loc == province or loc == city_district:
                score += 10
        ranked.append({'score': score, 'data': row})

    # 지역 점수로만 재정렬 (벡터 점수는 이미 상위 3개로 필터링됨)
    sorted_results = sorted(ranked, key=lambda x: x['score'], reverse=True)
    # 상위 3개 반환
    return [item['data'] for item in sorted_results[:3]]

def format_context_string(results: List) -> str:
    """
    LLM에 전달할 컨텍스트 문자열을 포맷팅합니다.
    """
    context_items = []
    # results의 각 항목은 (name, summary, url, prov, city) 튜플입니다.
    for i, (name, summary, url, prov, city) in enumerate(results, 1):
        region = f"{prov} {city}".strip() or "전국"
        context_items.append(
            # [최적화] 토큰을 아끼려면 summary를 잘라낼 수 있습니다. (예: {summary[:500]})
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
