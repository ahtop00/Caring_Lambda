# chatbot/repository/chat_repository.py
import json
import logging
from repository.connection import get_db_connection

logger = logging.getLogger()

def get_chat_history(session_id: str, limit: int = 5) -> list:
    """특정 세션의 최근 대화 내역 조회"""
    sql = """
        SELECT user_input, bot_response 
        FROM cbt_logs 
        WHERE session_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()
        # 최신순 -> 과거순 정렬
        return rows[::-1] if rows else []
    except Exception as e:
        logger.error(f"대화 내역 조회 실패: {e}")
        return []

def log_cbt_session(user_id: str, session_id: str, user_input: str, bot_response: dict, embedding: list):
    """상담 로그 및 벡터 DB 저장"""
    sql = """
        INSERT INTO cbt_logs (user_id, session_id, user_input, bot_response, embedding)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    user_id,
                    session_id,
                    user_input,
                    json.dumps(bot_response, ensure_ascii=False),
                    json.dumps(embedding)
                ))
                conn.commit()
                logger.info(f"CBT 로그 DB 저장 완료 (Session: {session_id})")
    except Exception as e:
        logger.error(f"CBT 로그 저장 실패: {e}")
