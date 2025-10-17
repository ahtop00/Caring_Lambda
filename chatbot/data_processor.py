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

def extract_locations(query: str) -> Optional[List[str]]:
    """쿼리에서 지역명을 추출합니다."""
    pattern = re.compile(r"(\S+[시군구도])(?:은|는|이|가|을|를|도|에|에서|의)?")
    matches = pattern.findall(query)
    return list(set(matches)) if matches else None

def rerank_results(results: List, locations: Optional[List[str]]) -> List:
    """검색 결과를 지역명 관련도에 따라 재순위화하고 상위 3개를 반환합니다."""
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
    """LLM에 전달할 컨텍스트 문자열을 포맷팅합니다."""
    context_items = []
    for i, (name, summary, url, prov, city) in enumerate(results, 1):
        region = f"{prov} {city}".strip() or "전국"
        context_items.append(
            f"문서 {i}:\n서비스명: {name}\n요약: {summary}\n지역: {region}\n링크: {url}\n"
        )
    return "\n".join(context_items)

def build_response(status_code: int, body: Dict) -> Dict[str, Any]:
    """API Gateway에 반환할 표준 응답을 생성합니다."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, ensure_ascii=False)
    }
