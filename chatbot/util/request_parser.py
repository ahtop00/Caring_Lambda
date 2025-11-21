# chatbot/util/request_parser.py
import json
import re
from typing import Dict, Any, List, Optional

def parse_search_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """검색 요청 Body를 파싱하고 필수 값을 추출합니다."""
    body = json.loads(event.get('body', '{}'))
    user_info = body.get('query1', '제공된 정보 없음')
    user_chat = body.get('query2')
    use_bedrock = body.get('bedrock', False)

    if not user_chat:
        raise ValueError("query2(사용자 질문)가 누락되었습니다.")

    return {
        "user_info": user_info,
        "user_chat": user_chat,
        "use_bedrock": use_bedrock
    }

def parse_reframing_body(event: Dict[str, Any]) -> str:
    """리프레이밍 요청 Body에서 사용자 입력을 추출합니다."""
    try:
        body = json.loads(event.get('body', '{}'))
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
