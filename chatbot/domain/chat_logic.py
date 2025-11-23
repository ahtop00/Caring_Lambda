# chatbot/domain/chat_logic.py
from fastapi import Depends
from schema.history import SessionListResponse, ChatHistoryResponse, ChatSessionItem, ChatMessage
from repository.chat_repository import ChatRepository, get_chat_repository

class ChatService:
    def __init__(self, chat_repo: ChatRepository):
        self.chat_repo = chat_repo

    def get_user_sessions(self, user_id: str) -> SessionListResponse:
        rows = self.chat_repo.get_user_sessions(user_id)
        sessions = []
        for r in rows:
            bot_res = r[3] if isinstance(r[3], dict) else {}
            distortion = bot_res.get("detected_distortion")
            tags = [distortion] if distortion and distortion != "분석 불가" else []

            sessions.append(ChatSessionItem(
                session_id=r[0],
                last_message=r[1],
                last_updated=r[2],
                distortion_tags=tags
            ))
        return SessionListResponse(sessions=sessions)

    def get_session_history(self, session_id: str, page: int) -> ChatHistoryResponse:
        size = 20
        offset = (page - 1) * size

        rows, total_cnt = self.chat_repo.get_session_messages(session_id, size, offset)

        messages = []
        for r in rows:
            bot_res = r[1] if isinstance(r[1], dict) else {}
            messages.append(ChatMessage(role="user", content=r[0], timestamp=r[2]))

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

# --- 의존성 주입용 함수 ---
def get_chat_service(chat_repo: ChatRepository = Depends(get_chat_repository)) -> ChatService:
    return ChatService(chat_repo)
