# chatbot/domain/chat_logic.py
from repository import chat_repository
from schema.history import SessionListResponse, ChatHistoryResponse, ChatSessionItem, ChatMessage

def get_user_sessions(user_id: str) -> SessionListResponse:
    """
    사용자의 채팅방 목록 조회 및 가공
    """
    rows = chat_repository.get_user_sessions(user_id)

    sessions = []
    for r in rows:
        # r: (session_id, user_input, created_at, bot_response_json)
        bot_res = r[3] if isinstance(r[3], dict) else {}

        # 왜곡 태그 처리
        distortion = bot_res.get("detected_distortion")
        tags = [distortion] if distortion and distortion != "분석 불가" else []

        sessions.append(ChatSessionItem(
            session_id=r[0],
            last_message=r[1],
            last_updated=r[2],
            distortion_tags=tags
        ))

    return SessionListResponse(sessions=sessions)

def get_session_history(session_id: str, page: int) -> ChatHistoryResponse:
    """
    특정 세션의 대화 내용 조회 및 가공
    """
    size = 20
    offset = (page - 1) * size

    rows, total_cnt = chat_repository.get_session_messages(session_id, size, offset)

    messages = []
    for r in rows:
        # r: (user_input, bot_response, created_at)
        bot_res = r[1] if isinstance(r[1], dict) else {}

        # 사용자 메시지
        messages.append(ChatMessage(
            role="user",
            content=r[0],
            timestamp=r[2]
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
