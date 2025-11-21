# chatbot/domain/reframing_logic.py
import logging
import json
import re

from service import llm_service
from util import request_parser, response_builder
from prompts.reframing import get_reframing_prompt

logger = logging.getLogger()

def process_reframing(event):
    """리프레이밍 요청 처리 메인 로직"""
    try:
        user_input = request_parser.parse_reframing_body(event)
        prompt = get_reframing_prompt(user_input)

        # 리프레이밍은 Gemini(Vertex AI) 사용을 기본으로 가정 (use_bedrock=False)
        llm_response = llm_service.get_llm_response(prompt, use_bedrock=False)

        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            response_data = json.loads(json_match.group(0))
        else:
            response_data = {
                "empathy": "응답 형식이 올바르지 않습니다.",
                "reframed_thought": llm_response
            }

        return response_builder.build_response(200, response_data)

    except ValueError as e:
        return response_builder.build_response(400, {'error': str(e)})
    except Exception as e:
        logger.error(f"리프레이밍 오류: {e}")
        raise e
