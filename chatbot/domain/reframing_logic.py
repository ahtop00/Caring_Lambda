# chatbot/domain/reframing_logic.py
import logging
import json
import re
import boto3
from fastapi import HTTPException

from config import config  # [수정] 중앙 설정 파일 임포트
from service import llm_service, db_service
from prompts.reframing import get_reframing_prompt
from schema.reframing import ReframingRequest

logger = logging.getLogger()

# SQS 클라이언트 초기화
sqs_client = boto3.client('sqs', region_name='ap-northeast-2')

def execute_reframing(request: ReframingRequest) -> dict:
    """
    CBT 리프레이밍 비즈니스 로직
    (응답 생성 후 저장은 SQS를 통해 비동기로 처리)
    """
    try:
        # [기억] DB에서 이번 세션의 대화 내역 조회
        history = db_service.get_chat_history(request.session_id, limit=5)

        # [생각] 프롬프트 구성 및 Gemini 호출
        prompt = get_reframing_prompt(request.user_input, history)

        # use_bedrock=False -> Gemini 사용
        llm_raw_response = llm_service.get_llm_response(prompt, use_bedrock=False)

        # JSON 파싱
        bot_response_dict = {}
        json_match = re.search(r'\{.*\}', llm_raw_response, re.DOTALL)
        if json_match:
            try:
                bot_response_dict = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                logger.error("LLM 응답 JSON 디코딩 실패")
                bot_response_dict = _create_fallback_response("JSON 형식 오류 발생")
        else:
            bot_response_dict = _create_fallback_response(llm_raw_response)

        # [비동기 저장 요청] SQS로 로그 데이터 전송
        if config.cbt_log_sqs_url:
            try:
                message_body = {
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "user_input": request.user_input,
                    "bot_response": bot_response_dict
                }
                sqs_client.send_message(
                    QueueUrl=config.cbt_log_sqs_url,  # [수정] config 사용
                    MessageBody=json.dumps(message_body, ensure_ascii=False)
                )
                logger.info(f"SQS 로그 저장 요청 전송 완료 (Session: {request.session_id})")
            except Exception as e:
                logger.error(f"SQS 전송 실패 (로그 유실 가능성 있음): {e}")
        else:
            logger.warning("config에 SQS URL이 설정되지 않아 로그 저장을 건너뜁니다.")

        return bot_response_dict

    except Exception as e:
        logger.error(f"리프레이밍 시스템 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def _create_fallback_response(msg: str) -> dict:
    return {
        "empathy": "답변을 처리하는 중 문제가 발생했습니다.",
        "detected_distortion": "분석 불가",
        "analysis": f"시스템 응답 오류: {msg[:100]}",
        "socratic_question": "다시 말씀해 주시겠어요?",
        "alternative_thought": ""
    }
