# chatbot/domain/reframing_logic.py
import logging
from fastapi import Depends

from exception import AppError
# from config import config  # SQS 설정 제거로 인해 불필요
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
        # self.sqs_client 제거 (동기 저장으로 변경)

    def execute_reframing(self, request: ReframingRequest) -> dict:
        """텍스트 기반 상담: LLM이 감정까지 추론"""
        try:
            # [기억]
            history = self.chat_repo.get_chat_history(request.session_id, limit=5)
            turn_count = self.chat_repo.get_session_turn_count(request.session_id)

            # [생각]
            prompt = get_reframing_prompt(request.user_input, history, turn_count)

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

            # [동기 저장] 임베딩 생성 및 DB 직납 (유령 읽기 방지)
            self._save_session_sync(
                user_id=request.user_id,
                session_id=request.session_id,
                user_input=request.user_input,
                bot_response=bot_response_dict,
                s3_url=None
            )

            return bot_response_dict

        except Exception as e:
            logger.error(f"리프레이밍 로직 오류: {e}", exc_info=True)
            raise AppError(500, "상담 답변 생성 실패", str(e))

    def execute_voice_reframing(self, request: VoiceReframingRequest) -> dict:
        """음성 기반 상담: 외부 분석 감정 데이터 활용"""
        try:
            # [기억]
            history = self.chat_repo.get_chat_history(request.session_id, limit=5)
            turn_count = self.chat_repo.get_session_turn_count(request.session_id)

            # [생각]
            prompt = get_voice_reframing_prompt(
                user_input=request.user_input,
                history=history,
                emotion=request.emotion,
                user_name=request.user_name or "내담자",
                turn_count=turn_count
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

            # [동기 저장] 임베딩 생성 및 DB 직납
            self._save_session_sync(
                user_id=request.user_id,
                session_id=request.session_id,
                user_input=request.user_input,
                bot_response=bot_response_dict,
                s3_url=request.s3_url
            )

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

    def _save_session_sync(self, user_id, session_id, user_input, bot_response, s3_url=None):
        """
        [동기 저장 헬퍼 함수]
        SQS를 거치지 않고 직접 임베딩을 생성하고 DB에 저장합니다.
        """
        # 임베딩 생성 (실패 시 0 벡터로 대체하여 흐름 끊기지 않게 함)
        embedding = []
        try:
            # 약 0.3~0.5초 소요 예상
            embedding = self.llm_service.get_embedding(user_input)
        except Exception as e:
            logger.error(f"임베딩 생성 실패 (저장은 계속 진행): {e}")
            embedding = [0.0] * 1024  # 1024차원 0 벡터

        # DB 저장
        try:
            self.chat_repo.log_cbt_session(
                user_id=user_id,
                session_id=session_id,
                user_input=user_input,
                bot_response=bot_response,
                embedding=embedding,
                s3_url=s3_url
            )
        except Exception as e:
            logger.error(f"DB 저장 실패: {e}")
            # 저장이 실패해도 사용자에게 답변은 전달되어야 하므로 예외를 다시 던지지 않음
            # 필요 시 raise하여 500 에러 처리 가능

# --- 의존성 주입용 함수 ---
def get_reframing_service(
        chat_repo: ChatRepository = Depends(get_chat_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> ReframingService:
    return ReframingService(chat_repo, llm_service)
