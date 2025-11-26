# chatbot/domain/reframing_logic.py
import logging
import json
import boto3
from fastapi import Depends

from exception import AppError
from config import config
from prompts.reframing import get_reframing_prompt, get_voice_reframing_prompt
from schema.reframing import ReframingRequest, VoiceReframingRequest
from repository.chat_repository import ChatRepository, get_chat_repository
from service.llm_service import LLMService, get_llm_service
from util.json_parser import parse_llm_json

logger = logging.getLogger()

class ReframingService:
    def __init__(self, chat_repo: ChatRepository, llm_service: LLMService):
        self.chat_repo = chat_repo
        self.llm_service = llm_service
        self.sqs_client = boto3.client('sqs', region_name='ap-northeast-2')

    def execute_reframing(self, request: ReframingRequest) -> dict:
        """텍스트 기반 상담: LLM이 감정까지 추론"""
        try:
            # [기억]
            history = self.chat_repo.get_chat_history(request.session_id, limit=5)

            # [생각]
            prompt = get_reframing_prompt(request.user_input, history)

            # [LLM]
            llm_raw_response = self.llm_service.get_llm_response(prompt, use_bedrock=False)

            # JSON 파싱 로직
            bot_response_dict = {}
            try:
                bot_response_dict = parse_llm_json(llm_raw_response)
            except ValueError:
                logger.warning("LLM 응답 파싱 실패 -> Fallback 사용")
                bot_response_dict = self._create_fallback_response(llm_raw_response)

            # [감정 데이터 처리]
            top_emotion = bot_response_dict.pop("top_emotion", "neutral")
            bot_response_dict["emotion"] = top_emotion

            # [비동기 저장 요청]
            self._send_log_to_sqs(request.user_id, request.session_id, request.user_input, bot_response_dict)

            return bot_response_dict

        except Exception as e:
            logger.error(f"리프레이밍 로직 오류: {e}", exc_info=True)
            raise AppError(500, "상담 답변 생성 실패", str(e))

    def execute_voice_reframing(self, request: VoiceReframingRequest) -> dict:
        """음성 기반 상담: 외부 분석 감정 데이터 활용"""
        try:
            # [기억]
            history = self.chat_repo.get_chat_history(request.session_id, limit=5)

            # 2. [생각]
            prompt = get_voice_reframing_prompt(
                user_input=request.user_input,
                history=history,
                emotion=request.emotion
            )

            # [LLM]
            llm_raw_response = self.llm_service.get_llm_response(prompt, use_bedrock=False)

            # [파싱]
            bot_response_dict = {}
            try:
                bot_response_dict = parse_llm_json(llm_raw_response)
            except ValueError:
                logger.warning("Voice LLM 응답 파싱 실패 -> Fallback 사용")
                bot_response_dict = self._create_fallback_response(llm_raw_response)

            # [감정 데이터 처리]
            raw_emotion = request.emotion.get("top_emotion", "neutral")
            bot_response_dict["emotion"] = raw_emotion

            # [비동기 저장 요청]
            self._send_log_to_sqs(request.user_id, request.session_id, request.user_input, bot_response_dict)

            return bot_response_dict

        except Exception as e:
            logger.error(f"음성 리프레이밍 로직 오류: {e}", exc_info=True)
            raise AppError(500, "음성 상담 답변 생성 실패", str(e))

    def _create_fallback_response(self, msg: str) -> dict:
        return {
            "empathy": "죄송해요, 잠시 생각이 꼬였나 봐요.",
            "detected_distortion": "분석 불가",
            "analysis": f"시스템 처리 중 오류가 발생했습니다. ({msg[:50]}...)",
            "socratic_question": "다시 한 번 말씀해 주시겠어요?",
            "alternative_thought": "",
            "emotion": "neutral"
        }

    def _send_log_to_sqs(self, user_id, session_id, user_input, bot_response):
        if config.cbt_log_sqs_url:
            try:
                message_body = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "user_input": user_input,
                    "bot_response": bot_response
                }
                self.sqs_client.send_message(
                    QueueUrl=config.cbt_log_sqs_url,
                    MessageBody=json.dumps(message_body, ensure_ascii=False)
                )
            except Exception as sqs_e:
                logger.error(f"SQS 전송 실패: {sqs_e}")

# --- 의존성 주입용 함수 ---
def get_reframing_service(
        chat_repo: ChatRepository = Depends(get_chat_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> ReframingService:
    return ReframingService(chat_repo, llm_service)
