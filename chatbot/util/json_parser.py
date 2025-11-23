# chatbot/util/json_parser.py
import json
import re
import logging

logger = logging.getLogger()

def parse_llm_json(text: str) -> dict:
    """
    LLM 응답 텍스트에서 JSON을 추출하여 딕셔너리로 변환하는 헬퍼 함수
    1. 마크다운 코드 블록(```json ... ```) 제거
    2. 순수 JSON 파싱 시도
    3. 실패 시 정규식으로 { ... } 구간 추출하여 재시도
    """
    if not text:
        raise ValueError("Empty LLM response")

    # 1. 마크다운 코드 블록 제거 (```json ... ```)
    cleaned_text = re.sub(r"```json\s*|\s*```", "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    try:
        # 2. 순수 JSON 파싱 시도
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        pass # 1차 실패 시 다음 단계로

    # 3. 실패 시 기존 방식(정규식)으로 가장 바깥쪽 { } 구간 탐색 시도
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    # 모든 시도 실패 시
    logger.error(f"JSON 파싱 실패. Raw Text(first 100 chars): {text[:100]}...")
    raise ValueError("LLM 응답에서 유효한 JSON 형식을 찾을 수 없습니다.")
