# chatbot/dependency.py
import logging
import psycopg2
from psycopg2 import pool
from typing import Generator
from config import config

logger = logging.getLogger()

# 전역 변수로 커넥션 풀 관리 (Lambda 컨테이너가 살아있는 동안 재사용됨)
_db_pool = None

def _init_db_pool():
    """커넥션 풀 초기화 (Lazy Initialization)"""
    global _db_pool
    if _db_pool is None:
        try:
            logger.info("DB 커넥션 풀 초기화 시도...")
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=config.db_host,
                database=config.db_name,
                user=config.db_user,
                password=config.db_password,
                connect_timeout=5
            )
            logger.info("DB 커넥션 풀 생성 완료.")
        except Exception as e:
            logger.error(f"DB 커넥션 풀 생성 실패: {e}")
            raise e

def get_db_conn() -> Generator:
    """
    FastAPI Dependency: 커넥션 풀에서 연결을 빌려오고, 사용 후 반납(putconn)합니다.
    """
    global _db_pool

    # 풀이 없으면 생성
    if _db_pool is None:
        _init_db_pool()

    conn = None
    try:
        # 연결 빌리기
        conn = _db_pool.getconn()
        yield conn
    finally:
        # 연결 반납하기
        if conn:
            _db_pool.putconn(conn)
