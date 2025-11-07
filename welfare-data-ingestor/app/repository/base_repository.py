# app/repository/base_repository.py
# -*- coding: utf-8 -*-
import logging
import psycopg2

logger = logging.getLogger()

class BaseRepository:
    """
    데이터베이스 연결, 커밋, 롤백, 종료 등
    모든 Repository가 공통으로 사용할 부모 클래스
    """

    def __init__(self, db_config: dict):
        """
        Repository 초기화 시 DB 연결을 생성합니다.
        :param db_config: {'host', 'dbname', 'user', 'password'} 딕셔너리
        """
        try:
            logger.info(f"데이터베이스 연결 시도... (Host: {db_config.get('host')})")
            # DB 연결
            self.conn = psycopg2.connect(
                host=db_config['host'],
                database=db_config['dbname'],
                user=db_config['user'],
                password=db_config['password'],
                connect_timeout=10
            )
            self.cur = self.conn.cursor()
            logger.info("데이터베이스 연결 성공.")
        except psycopg2.Error as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise e # 초기화 실패 시 람다 실행 중단

    def commit(self):
        """현재 트랜잭션을 커밋합니다."""
        try:
            self.conn.commit()
        except psycopg2.Error as e:
            logger.error(f"DB 커밋 실패: {e}")
            self.conn.rollback() # 커밋 실패 시 롤백

    def rollback(self):
        """현재 트랜잭션을 롤백합니다."""
        try:
            self.conn.rollback()
            logger.warning("트랜잭션을 롤백했습니다.")
        except psycopg2.Error as e:
            logger.error(f"DB 롤백 실패: {e}")

    def close(self):
        """데이터베이스 연결을 종료합니다."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("데이터베이스 연결을 종료했습니다.")
