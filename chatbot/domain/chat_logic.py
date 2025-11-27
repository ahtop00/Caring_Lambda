# chatbot/domain/chat_logic.py
import logging
import json
from fastapi import Depends

from exception import AppError
from schema.history import SessionListResponse, ChatHistoryResponse, ChatSessionItem, ChatMessage
from repository.chat_repository import ChatRepository, get_chat_repository

logger = logging.getLogger()

class ChatService:
    def __init__(self, chat_repo: ChatRepository):
        self.chat_repo = chat_repo

    def get_user_sessions(self, user_id: str) -> SessionListResponse:
        try:
            rows = self.chat_repo.get_user_sessions(user_id)
            sessions = []
            for r in rows:
                # r: (session_id, user_input, created_at, bot_response_json)
                bot_res = r[3]
                if isinstance(bot_res, str):
                    try:
                        bot_res = json.loads(bot_res)
                    except:
                        bot_res = {}
                elif not isinstance(bot_res, dict):
                    bot_res = {}

                distortion = bot_res.get("detected_distortion")
                tags = [distortion] if distortion and distortion != "분석 불가" else []
                emotion = bot_res.get("emotion")

                sessions.append(ChatSessionItem(
                    session_id=r[0],
                    last_message=r[1],
                    last_updated=r[2],
                    distortion_tags=tags,
                    emotion=emotion
                ))
            return SessionListResponse(sessions=sessions)

        except Exception as e:
            logger.error(f"채팅방 목록 조회 중 오류 발생: {e}", exc_info=True)
            raise AppError(
                status_code=500,
                message="채팅방 목록을 불러오는 중 문제가 발생했습니다.",
                detail=str(e)
            )

    def get_session_history(self, session_id: str, page: int) -> ChatHistoryResponse:
        try:
            size = 20
            offset = (page - 1) * size

            # DB에서 최신순(DESC)으로 limit만큼 가져옴
            rows, total_cnt = self.chat_repo.get_session_messages(session_id, size, offset)

            if rows:
                rows = rows[::-1]

            messages = []
            for r in rows:
                # r: (user_input, bot_response, created_at, s3_url)
                bot_res = r[1] if isinstance(r[1], dict) else {}
                s3_url = r[3]

                # 사용자 메시지
                messages.append(ChatMessage(
                    role="user",
                    content=r[0],
                    timestamp=r[2],
                    s3_url=s3_url
                ))

                # 봇 메시지
                bot_content = f"{bot_res.get('empathy', '')} {bot_res.get('socratic_question', '')}".strip()
                messages.append(ChatMessage(
                    role="assistant",
                    content=bot_content,
                    timestamp=r[2],
                    distortion=bot_res.get("detected_distortion"),
                    empathy=bot_res.get("empathy")
                ))

            return ChatHistoryResponse(
                session_id=session_id,
                messages=messages,
                total_page=(total_cnt // size) + 1 if total_cnt > 0 else 1,
                current_page=page
            )

        except Exception as e:
            logger.error(f"채팅 상세 내역 조회 중 오류 발생: {e}", exc_info=True)
            raise AppError(
                status_code=500,
                message="대화 내용을 불러오는 중 문제가 발생했습니다.",
                detail=str(e)
            )

# --- 의존성 주입용 함수 ---
def get_chat_service(chat_repo: ChatRepository = Depends(get_chat_repository)) -> ChatService:
    return ChatService(chat_repo)
