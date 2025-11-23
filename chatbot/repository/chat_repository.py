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

def get_user_sessions(user_id: str) -> list:
    """
    사용자의 채팅방 목록 조회 (세션별 가장 최근 메시지 1개)
    """
    # 각 session_id별로 가장 최근(created_at DESC) 로우 하나만 뽑는 윈도우 함수 쿼리
    sql = """
        WITH recent_logs AS (
            SELECT 
                session_id,
                user_input,
                created_at,
                bot_response,
                ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY created_at DESC) as rn
            FROM cbt_logs
            WHERE user_id = %s
        )
        SELECT session_id, user_input, created_at, bot_response
        FROM recent_logs
        WHERE rn = 1
        ORDER BY created_at DESC;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"세션 목록 조회 실패: {e}")
        return []

def get_session_messages(session_id: str, limit: int, offset: int) -> tuple:
    """
    특정 세션의 대화 상세 조회 (페이징)
    Return: (rows, total_count)
    """
    count_sql = "SELECT COUNT(*) FROM cbt_logs WHERE session_id = %s"

    # 시간순 정렬 (과거 -> 현재)
    data_sql = """
        SELECT user_input, bot_response, created_at 
        FROM cbt_logs
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s OFFSET %s
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(count_sql, (session_id,))
                total_count = cur.fetchone()[0]

                cur.execute(data_sql, (session_id, limit, offset))
                rows = cur.fetchall()

        return rows, total_count
    except Exception as e:
        logger.error(f"상세 대화 조회 실패: {e}")
        return [], 0
