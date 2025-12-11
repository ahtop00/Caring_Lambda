# chatbot/repository/chat_repository.py
import json
import logging
from fastapi import Depends
from dependency import get_db_conn

logger = logging.getLogger()

class ChatRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_chat_history(self, session_id: str, limit: int = 5) -> list:
        """특정 세션의 최근 대화 내역 조회"""
        sql = """
            SELECT user_input, bot_response 
            FROM cbt_logs 
            WHERE session_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()
            return rows[::-1] if rows else []
        except Exception as e:
            logger.error(f"대화 내역 조회 실패: {e}")
            return []

    def log_cbt_session(self, user_id: str, session_id: str, user_input: str, bot_response: dict, embedding: list, s3_url: str = None):
        sql = """
            INSERT INTO cbt_logs (user_id, session_id, user_input, bot_response, embedding, s3_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    user_id,
                    session_id,
                    user_input,
                    json.dumps(bot_response, ensure_ascii=False),
                    json.dumps(embedding),
                    s3_url  # [핵심] DB에 저장 (없으면 None)
                ))
                self.conn.commit()
                logger.info(f"CBT 로그 DB 저장 완료 (Session: {session_id})")
        except Exception as e:
            logger.error(f"CBT 로그 저장 실패: {e}")
            self.conn.rollback()

    def get_user_sessions(self, user_id: str) -> list:
        """사용자의 채팅방 목록 조회"""
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
            with self.conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"세션 목록 조회 실패: {e}")
            return []

    def get_session_messages(self, session_id: str, limit: int, offset: int) -> tuple:
        count_sql = "SELECT COUNT(*) FROM cbt_logs WHERE session_id = %s"

        data_sql = """
            SELECT user_input, bot_response, created_at, s3_url
            FROM cbt_logs
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(count_sql, (session_id,))
                total_count = cur.fetchone()[0]

                cur.execute(data_sql, (session_id, limit, offset))
                rows = cur.fetchall()

            return rows, total_count
        except Exception as e:
            logger.error(f"상세 대화 조회 실패: {e}")
            return [], 0

    def get_session_turn_count(self, session_id: str) -> int:
        """session_id에 해당 하는 세션의 대화 횟수 조회"""
        sql = "SELECT COUNT(*) FROM cbt_logs WHERE session_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (session_id,))
                result = cur.fetchone()
                # 결과가 없으면 0, 있으면 개수 반환
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"세션 턴 수 조회 실패: {e}")
            return 0

# --- 의존성 주입용 헬퍼 함수 ---
def get_chat_repository(conn=Depends(get_db_conn)) -> ChatRepository:
    return ChatRepository(conn)
