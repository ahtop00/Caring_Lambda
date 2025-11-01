# -*- coding: utf-8 -*-
import logging
import psycopg2
from psycopg2 import sql

logger = logging.getLogger()

class WelfareRepository:
    """
    복지 서비스 데이터베이스(PostgreSQL) 연동을 담당하는 클래스 (Repository Pattern)
    """

    SQL_FIND_EXISTING_IDS = """
        SELECT id FROM welfare_services WHERE id = ANY(%s);
    """

    SQL_INSERT_SERVICE = """
        INSERT INTO welfare_services (
            id, service_name, service_summary, embedding,
            province, city_district, department_name,
            target_audience, life_cycle, interest_theme,
            support_cycle, support_type, application_method,
            last_modified_date, detail_link
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    def __init__(self, db_config):
        """
        Repository 초기화 시 DB 연결을 생성합니다.
        db_config: {'host', 'dbname', 'user', 'password'} 딕셔너리
        """
        try:
            logger.info(f"데이터베이스 연결 시도... (Host: {db_config.get('host')})")
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
            raise e

    def get_existing_ids(self, id_list):
        """ID 리스트를 받아 DB에 이미 존재하는 ID의 set을 반환합니다."""
        if not id_list:
            return set()
        try:
            self.cur.execute(self.SQL_FIND_EXISTING_IDS, (id_list,))
            existing_ids = {row[0] for row in self.cur.fetchall()}
            logger.info(f"DB 조회 결과, {len(existing_ids)}개의 서비스가 이미 존재합니다.")
            return existing_ids
        except psycopg2.Error as e:
            logger.error(f"기존 ID 조회 중 DB 오류: {e}")
            self.conn.rollback()
            return set()

    def _format_date(self, ymd_string):
        """'YYYYMMDD' 형식의 문자열을 'YYYY-MM-DD'로 변환합니다."""
        if ymd_string and len(ymd_string) == 8:
            try:
                return f"{ymd_string[:4]}-{ymd_string[4:6]}-{ymd_string[6:]}"
            except Exception:
                pass
        return None # 변환 실패 시 None 반환

    def _split_and_filter(self, text_array_string):
        """'A,B,C' 형식의 문자열을 리스트 ['A', 'B', 'C']로 변환합니다."""
        if not text_array_string:
            return []
        return list(filter(None, text_array_string.split(',')))

    def insert_service(self, service, embedding):
        """단일 서비스 데이터와 임베딩 벡터를 DB에 INSERT합니다."""
        try:
            last_modified_date = self._format_date(service.get('lastModYmd'))

            params_for_db = (
                service.get('servId'),
                service.get('servNm'),
                service.get('servDgst'),
                embedding,
                service.get('ctpvNm'),
                service.get('sggNm'),
                service.get('bizChrDeptNm'),
                self._split_and_filter(service.get('trgterIndvdlNmArray')),
                self._split_and_filter(service.get('lifeNmArray')),
                self._split_and_filter(service.get('intrsThemaNmArray')),
                service.get('sprtCycNm'),
                service.get('srvPvsnNm'),
                service.get('aplyMtdNm'),
                last_modified_date,
                service.get('servDtlLink')
            )

            self.cur.execute(self.SQL_INSERT_SERVICE, params_for_db)

        except psycopg2.Error as e:
            logger.error(f"DB INSERT 중 오류 (ServiceId: {service.get('servId')}): {e}")
        except Exception as e:
             logger.error(f"DB 파라미터 준비 중 오류 (ServiceId: {service.get('servId')}): {e}")


    def commit(self):
        """현재 트랜잭션을 커밋합니다."""
        try:
            self.conn.commit()
        except psycopg2.Error as e:
            logger.error(f"DB 커밋 실패: {e}")
            self.conn.rollback()

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
