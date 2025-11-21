# chatbot/domain/reframing_logic.py
import logging
import json
import re
from fastapi import HTTPException

from service import llm_service
from prompts.reframing import get_reframing_prompt

logger = logging.getLogger()

def execute_reframing(user_input: str) -> dict:
    """리프레이밍 비즈니스 로직"""
    try:
        prompt = get_reframing_prompt(user_input)

        # Gemini 사용 (use_bedrock=False)
        llm_response = llm_service.get_llm_response(prompt, use_bedrock=False)

        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            # JSON 파싱 실패 시 텍스트라도 반환
            return {
                "empathy": "응답 형식이 올바르지 않습니다.",
                "reframed_thought": llm_response
            }

    except Exception as e:
        logger.error(f"리프레이밍 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
