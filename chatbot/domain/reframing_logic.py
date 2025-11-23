# chatbot/domain/reframing_logic.py
import logging
import json
import re
import boto3
from fastapi import HTTPException, Depends

from config import config
from prompts.reframing import get_reframing_prompt
from schema.reframing import ReframingRequest
from repository.chat_repository import ChatRepository, get_chat_repository
from service.llm_service import LLMService, get_llm_service

logger = logging.getLogger()

class ReframingService:
    def __init__(self, chat_repo: ChatRepository, llm_service: LLMService):
        self.chat_repo = chat_repo
        self.llm_service = llm_service
        self.sqs_client = boto3.client('sqs', region_name='ap-northeast-2')

    def execute_reframing(self, request: ReframingRequest) -> dict:
        try:
            # [기억] 의존성 주입된 Repo 사용
            history = self.chat_repo.get_chat_history(request.session_id, limit=5)

            # [생각]
            prompt = get_reframing_prompt(request.user_input, history)

            # [LLM] 의존성 주입된 Service 사용
            llm_raw_response = self.llm_service.get_llm_response(prompt, use_bedrock=False)

            # JSON 파싱
            bot_response_dict = {}
            json_match = re.search(r'\{.*\}', llm_raw_response, re.DOTALL)
            if json_match:
                try:
                    bot_response_dict = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    bot_response_dict = self._create_fallback_response("JSON 형식 오류")
            else:
                bot_response_dict = self._create_fallback_response(llm_raw_response)

            # [비동기 저장 요청]
            if config.cbt_log_sqs_url:
                try:
                    message_body = {
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "user_input": request.user_input,
                        "bot_response": bot_response_dict
                    }
                    self.sqs_client.send_message(
                        QueueUrl=config.cbt_log_sqs_url,
                        MessageBody=json.dumps(message_body, ensure_ascii=False)
                    )
                except Exception as e:
                    logger.error(f"SQS 전송 실패: {e}")

            return bot_response_dict

        except Exception as e:
            logger.error(f"리프레이밍 오류: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def _create_fallback_response(self, msg: str) -> dict:
        return {
            "empathy": "문제가 발생했습니다.",
            "detected_distortion": "분석 불가",
            "analysis": f"오류: {msg[:100]}",
            "socratic_question": "다시 말씀해 주세요.",
            "alternative_thought": ""
        }

# --- 의존성 주입용 함수 ---
def get_reframing_service(
        chat_repo: ChatRepository = Depends(get_chat_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> ReframingService:
    return ReframingService(chat_repo, llm_service)
