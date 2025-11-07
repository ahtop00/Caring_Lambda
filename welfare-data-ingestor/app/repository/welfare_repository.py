# app/repository/welfare_repository.py
# -*- coding: utf-8 -*-
import logging
import psycopg2
from psycopg2.extras import execute_values # 일괄 삽입(Batch)을 위해 임포트
from typing import List, Tuple, Set

# app 패키지 내부의 모듈을 임포트
try:
    from app.repository.base_repository import BaseRepository
    from app.dto.common_dto import CommonServiceDTO
except ImportError:
    # 로컬 테스트 등을 위한 예외 처리
    from base_repository import BaseRepository
    from ..common_dto import CommonServiceDTO


logger = logging.getLogger()

class WelfareRepository(BaseRepository):
    """
    'welfare_services' 테이블 관련 로직을 담당 (BaseRepository 상속)
    """

    # SQL 쿼리 정의
    SQL_FIND_EXISTING_IDS = """
        SELECT id FROM welfare_services WHERE id = ANY(%s);
    """

    # 일괄 삽입(Batch Insert)용 SQL
    SQL_INSERT_SERVICE_BATCH = """
        INSERT INTO welfare_services (
            id, service_name, service_summary, embedding,
            province, city_district, department_name,
            target_audience, life_cycle, interest_theme,
            support_cycle, support_type, application_method,
            last_modified_date, detail_link
        )
        VALUES %s;
    """ # execute_values가 %s를 값 리스트로 치환합니다.

    def __init__(self, db_config: dict):
        """
        부모 클래스(BaseRepository)의 __init__을 호출하여 DB 연결을 설정합니다.
        """
        super().__init__(db_config)

    def get_existing_ids(self, id_list: List[str]) -> Set[str]:
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
            self.rollback() # 오류 발생 시 현재 트랜잭션 롤백
            return set() # 실패 시 비어있는 set 반환

    # [신규] 일괄 삽입 메소드
    def insert_services_batch(self, data_list: List[Tuple[CommonServiceDTO, List[float]]]) -> int:
        """
        여러 서비스 DTO와 임베딩 리스트를 받아 DB에 일괄 삽입(Batch)합니다.
        (기존의 단일 insert_service를 대체합니다)

        :param data_list: (CommonServiceDTO, embedding) 튜플의 리스트
        :return: 삽입된 행의 수
        """
        if not data_list:
            return 0

        try:
            # DB에 삽입할 값(tuple) 리스트 생성
            # DTO에서 직접 값을 꺼내 SQL 순서에 맞게 튜플 생성
            params_list = [
                (
                    dto.service_id,
                    dto.service_name,
                    dto.service_summary,
                    embedding, # 임베딩 (List[float])
                    dto.province,
                    dto.city_district,
                    dto.department_name,
                    dto.target_audience,    # List[str] (PostgreSQL의 text[] 타입과 호환됨)
                    dto.life_cycle,         # List[str]
                    dto.interest_theme,     # List[str]
                    dto.support_cycle,
                    dto.support_type,
                    dto.application_method,
                    dto.last_modified_date, # DTO 생성 시 'YYYY-MM-DD' 등으로 포맷팅됨
                    dto.detail_link
                )
                for dto, embedding in data_list # (dto, embedding) 튜플을 순회
            ]

            # psycopg2.extras.execute_values를 사용하여 일괄 INSERT 실행
            execute_values(
                self.cur,
                self.SQL_INSERT_SERVICE_BATCH,
                params_list,
                page_size=100 # 100개씩 나눠서 실행
            )

            inserted_count = len(params_list)
            logger.info(f"{inserted_count}개의 신규 서비스를 DB에 일괄 삽입했습니다.")
            return inserted_count

        except psycopg2.Error as e:
            logger.error(f"DB 일괄 INSERT 중 오류: {e}")
            self.rollback() # 일괄 삽입 실패 시 롤백
            return 0 # 0개 삽입됨을 반환
        except Exception as e:
            logger.error(f"DB 파라미터 준비 중 오류: {e}")
            self.rollback()
            return 0
