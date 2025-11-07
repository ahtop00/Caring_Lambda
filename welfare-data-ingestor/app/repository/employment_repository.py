# -*- coding: utf-8 -*-
import logging
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Tuple, Set, Optional
import datetime # 날짜 파싱을 위해 임포트

try:
    from app.repository.base_repository import BaseRepository
    from app.employment_dto import JobOpeningDTO
except ImportError:
    from base_repository import BaseRepository
    from ..employment_dto import JobOpeningDTO

logger = logging.getLogger()

class EmploymentRepository(BaseRepository):
    """
    'employment_jobs' 테이블 관련 로직 (수정)
    """

    # [수정] id 컬럼 제거 (자동 생성), term_date_* 컬럼 추가
    SQL_INSERT_JOBS_BATCH = """
        INSERT INTO employment_jobs (
            company_name, job_title, job_description, embedding,
            job_type, salary, salary_type, location, 
            required_skills, required_career, required_education,
            last_modified_date, detail_link,
            term_date_start, term_date_end
        )
        VALUES %s;
    """

    # [신규] 만료된 공고 삭제 쿼리
    SQL_DELETE_EXPIRED_JOBS = """
        DELETE FROM employment_jobs WHERE term_date_end < CURRENT_DATE;
    """

    def __init__(self, db_config: dict):
        super().__init__(db_config)

    def get_existing_ids(self, id_list: List[str]) -> Set[str]:
        """
        [수정]
        요구사항(겹치는 게 있을 수 있음)에 따라, 중복 검사를 수행하지 않고
        항상 모든 데이터를 신규로 취급하여 삽입합니다.
        """
        return set()

    def _parse_term_date(self, term_date_str: Optional[str]) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
        [신규]
        "YYYY-MM-DD~YYYY-MM-DD" 형식의 문자열을 파싱하여
        (start_date, end_date) 튜플로 반환합니다.
        """
        if not term_date_str or '~' not in term_date_str:
            return None, None
        try:
            start_str, end_str = term_date_str.split('~')
            start_date = datetime.date.fromisoformat(start_str)
            end_date = datetime.date.fromisoformat(end_str)
            return start_date, end_date
        except (ValueError, TypeError):
            logger.warning(f"[Employment] termDate 파싱 실패: {term_date_str}")
            return None, None

    def _build_params_list(self, data_list: List[Tuple[JobOpeningDTO, List[float]]]) -> List[tuple]:
        """[수정] DTO를 DB 튜플 리스트로 변환 (termDate 파싱 포함)"""
        params_list = []
        for dto, embedding in data_list:

            # termDate 파싱 로직 호출
            term_start, term_end = self._parse_term_date(dto.term_date_str)

            params = (
                # dto.job_id 제거됨
                dto.company_name,
                dto.job_title,
                dto.job_description,
                embedding,
                dto.job_type,
                dto.salary,
                dto.salary_type,
                dto.location,
                dto.required_skills,
                dto.required_career,
                dto.required_education,
                dto.last_modified_date,
                dto.detail_link,
                term_start, # [신규]
                term_end    # [신규]
            )
            params_list.append(params)
        return params_list

    def insert_services_batch(self, data_list: List[Tuple[JobOpeningDTO, List[float]]]) -> int:
        """[수정] 구인 정보 DTO 리스트를 DB에 일괄 삽입"""
        if not data_list:
            return 0

        try:
            params_list = self._build_params_list(data_list)

            execute_values(
                self.cur,
                self.SQL_INSERT_JOBS_BATCH,
                params_list,
                page_size=100
            )

            inserted_count = len(params_list)
            logger.info(f"[Employment] {inserted_count}개의 신규 Job을 DB에 일괄 삽입했습니다.")
            return inserted_count
        except psycopg2.Error as e:
            # (중요) 만약 중복 삽입을 막기 위해 UNIQUE 제약조건을 사용했다면,
            # 여기서 e.pgcode == '23505' (unique_violation)를 확인하고
            # 오류 로깅 대신 무시(pass)하도록 처리할 수 있습니다.
            logger.error(f"[Employment] DB 일괄 INSERT 중 오류: {e}")
            self.rollback()
            return 0
        except Exception as e:
            logger.error(f"[Employment] DB 파라미터 준비 중 오류: {e}")
            self.rollback()
            return 0

    def delete_expired_jobs(self) -> int:
        """
        [신규]
        term_date_end가 오늘(CURRENT_DATE)보다 이전인 모든 공고를 삭제합니다.
        Processor가 작업 시작 전에 호출합니다.
        """
        try:
            self.cur.execute(self.SQL_DELETE_EXPIRED_JOBS)
            deleted_count = self.cur.rowcount
            if deleted_count > 0:
                logger.info(f"[Employment] 만료된 공고 {deleted_count}개를 삭제했습니다.")
            # (중요) 이 작업은 Processor의 메인 트랜잭션에 포함되므로
            # 여기서 커밋하지 않고 Processor가 커밋하도록 둡니다.
            return deleted_count
        except psycopg2.Error as e:
            logger.error(f"[Employment] 만료된 공고 삭제 중 DB 오류: {e}")
            self.rollback() # 오류 발생 시 롤백
            return 0
