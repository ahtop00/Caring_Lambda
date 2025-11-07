# -*- coding: utf-8 -*-
import logging
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Tuple, Set, Optional
import datetime # 날짜 파싱을 위해 임포트

try:
    from app.repository.base_repository import BaseRepository
    from app.dto.employment_dto import JobOpeningDTO
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
            term_date_start, term_date_end,
            term_date_str 
        )
        VALUES %s;
    """

    SQL_DELETE_EXPIRED_JOBS = """
        DELETE FROM employment_jobs WHERE term_date_end < CURRENT_DATE;
    """

    SQL_FIND_EXISTING_KEYS = """
        SELECT company_name, job_title, term_date_str, salary FROM employment_jobs;
    """


    def __init__(self, db_config: dict):
        super().__init__(db_config)

    def get_existing_ids(self, id_list: List[str]) -> Set[str]:
        """
        Delta(차이) 업데이트를 위해 중복 검사를 수행하지 않습니다.
        (중복 검사는 insert_services_batch에서 복합 키로 수행)
        """
        return set()

    def _parse_term_date(self, term_date_str: Optional[str]) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
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
        """DTO를 DB 튜플 리스트로 변환 (termDate 파싱 포함)"""
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
                term_start,
                term_end,
                dto.term_date_str
            )
            params_list.append(params)
        return params_list

    def _get_existing_keys_set(self) -> Set[str]:
        """[신규] 현재 DB에 저장된 모든 공고의 복합 키 Set을 반환"""
        try:
            self.cur.execute(self.SQL_FIND_EXISTING_KEYS)
            existing_keys = set()
            for row in self.cur.fetchall():
                # DTO의 get_composite_key와 동일한 로직으로 키 생성
                # DB 순서: company_name(0), job_title(1), term_date_str(2), salary(3)
                key = f"{row[0] or ''}|{row[1] or ''}|{row[2] or ''}|{row[3] or ''}"
                existing_keys.add(key)
            logger.info(f"[Employment] DB에서 {len(existing_keys)}개의 기존 복합 키 조회 완료.")
            return existing_keys
        except psycopg2.Error as e:
            logger.error(f"[Employment] 기존 복합 키 조회 중 DB 오류: {e}")
            self.rollback() # 조회 실패 시 트랜잭션 롤백
            raise e # 상위로 오류 전파

    def insert_services_batch(self, data_list: List[Tuple[JobOpeningDTO, List[float]]]) -> List[JobOpeningDTO]:
        """구인 정보 DTO 리스트를 DB에 일괄 삽입 (Delta 로직)"""
        if not data_list:
            return []

        try:
            # 1. DB의 기존 복합 키 조회
            existing_keys = self._get_existing_keys_set()
        except psycopg2.Error:
            # _get_existing_keys_set에서 이미 롤백하고 오류 로깅함
            return [] # 빈 리스트 반환

        new_data_list_with_embeddings = [] # (dto, embedding)
        new_dtos_for_publish = []        # dto

        # 2. API DTOs와 DB DTOs 비교
        for dto, embedding in data_list:
            key = dto.get_composite_key()
            if key not in existing_keys:
                new_data_list_with_embeddings.append((dto, embedding))
                new_dtos_for_publish.append(dto)

        if not new_data_list_with_embeddings:
            logger.info("[Employment] 신규로 삽입할 Job이 없습니다 (모두 중복).")
            return []
        # ---------------------------

        try:
            # 신규 데이터만 DB에 삽입
            params_list = self._build_params_list(new_data_list_with_embeddings)

            execute_values(
                self.cur,
                self.SQL_INSERT_JOBS_BATCH,
                params_list,
                page_size=100
            )

            inserted_count = len(params_list)
            logger.info(f"[Employment] {inserted_count}개의 신규 Job을 DB에 일괄 삽입했습니다.")

            # 4. 삽입된 '신규' DTO 리스트를 반환 (SQS 발행용)
            return new_dtos_for_publish
        except psycopg2.Error as e:
            logger.error(f"[Employment] DB 일괄 INSERT 중 오류: {e}")
            self.rollback()
            return []
        except Exception as e:
            logger.error(f"[Employment] DB 파라미터 준비 중 오류: {e}")
            self.rollback()
            return []

    def delete_expired_jobs(self) -> int:
        """
        term_date_end가 오늘(CURRENT_DATE)보다 이전인 모든 공고를 삭제합니다.
        (TRUNCATE 대신 Delta 유지를 위해 이 로직 사용)
        """
        try:
            self.cur.execute(self.SQL_DELETE_EXPIRED_JOBS)
            deleted_count = self.cur.rowcount
            if deleted_count > 0:
                logger.info(f"[Employment] 만료된 공고 {deleted_count}개를 삭제했습니다.")
            return deleted_count
        except psycopg2.Error as e:
            logger.error(f"[Employment] 만료된 공고 삭제 중 DB 오류: {e}")
            self.rollback() # 오류 발생 시 롤백
            return 0
