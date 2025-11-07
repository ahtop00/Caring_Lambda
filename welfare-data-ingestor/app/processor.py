# -*- coding: utf-8 -*-
import logging
import time
from typing import List, Tuple
from botocore.exceptions import ClientError

# app 내부 모듈 임포트
from app.fetcher.base_fetcher import BaseWelfareFetcher
from app.repository.base_repository import BaseRepository
from app.service.embedding_service import EmbeddingService
from app.service.notification_service import NotificationService
logger = logging.getLogger()

class IngestProcessor:
    """
    데이터 수집/처리/저장의 핵심 비즈니스 로직(Orchestration)을 담당.
    """

    def __init__(self,
                 repo: BaseRepository,
                 embedder: EmbeddingService,
                 publisher: NotificationService,
                 page_config: dict):
        self.repo = repo
        self.embedder = embedder
        self.publisher = publisher
        self.start_page = page_config.get('start_page', 1)
        self.page_limit = page_config.get('page_limit', 5)

    def run_for_fetcher(self, fetcher: BaseWelfareFetcher, event_params: dict):
        """
        주입된 단일 Fetcher에 대해 수집 작업을 실행합니다.
        """
        fetcher_name = fetcher.__class__.__name__
        logger.info(f"--- Processor '{fetcher_name}' 작업 시작 ---")

        # --- [신규] 만료 데이터 삭제 로직 ---
        # repo 객체에 'delete_expired_jobs' 메소드가 있는지 확인 (덕 타이핑)
        if hasattr(self.repo, 'delete_expired_jobs') and callable(self.repo.delete_expired_jobs):
            logger.info(f"[{fetcher_name}] 만료된 데이터 삭제 작업 시작...")
            try:
                # [수정] TRUNCATE 대신 만료된 공고만 삭제 (Delta 유지)
                self.repo.delete_expired_jobs()
            except Exception as e:
                logger.error(f"[{fetcher_name}] 만료 데이터 삭제 중 오류: {e}. 작업을 롤백합니다.")
                self.repo.rollback()
                return 0 # 만료 데이터 삭제 실패 시 해당 Fetcher 작업 중단
        # ------------------------------------

        total_inserted_count = 0

        page = self.start_page

        while True:
            logger.info(f"--- API 페이지 {page} 조회 시작 ({fetcher_name}) ---")

            # Fetch (DTO 리스트 반환)
            service_dtos: List = fetcher.fetch_services_by_page(page, event_params)
            if not service_dtos:
                logger.info(f"페이지 {page}에서 더 이상 조회된 서비스가 없어 '{fetcher_name}' 작업을 중단합니다.")
                break # 여기가 루프의 유일한 탈출 지점

            # Filter (DTO의 service_id 또는 job_id 사용)
            # (EmploymentRepository는 get_existing_ids에서 항상 빈 set을 반환함)
            # (WelfareRepository는 실제 중복 검사를 수행함)
            ids_from_api = [dto.service_id for dto in service_dtos if hasattr(dto, 'service_id')]

            existing_ids = set()
            if ids_from_api:
                # Welfare의 경우에만 중복 검사 (Employment는 빈 set 반환)
                existing_ids = self.repo.get_existing_ids(ids_from_api)

            # DTO 리스트 필터링 (Welfare의 경우)
            if hasattr(service_dtos[0], 'service_id'):
                new_service_dtos = [dto for dto in service_dtos if dto.service_id not in existing_ids]
            else:
                # JobOpeningDTO의 경우, get_existing_ids가 빈 set을 반환하므로 항상 모든 DTO가 포함됨
                # (실제 중복 필터링은 repo.insert_services_batch에서 수행)
                new_service_dtos = service_dtos

            if not new_service_dtos:
                logger.info(f"페이지 {page}에는 (API 응답 기준) 신규 서비스가 없습니다.")
                page += 1 # [수정] 다음 페이지로
                continue

            # Embed
            logger.info(f"페이지 {page}에서 {len(new_service_dtos)}개의 신규 후보 서비스를 발견했습니다. 임베딩을 시작합니다.")
            data_to_insert: List[Tuple] = self._create_embeddings(new_service_dtos)
            if not data_to_insert:
                logger.info("임베딩에 성공한 데이터가 없습니다.")
                page += 1 # [수정] 다음 페이지로
                continue

            # Save & Publish (트랜잭션)
            # (기존 _save_and_publish 헬퍼 메소드 호출)
            page_inserted_count = self._save_and_publish(data_to_insert)

            # _save_and_publish가 실패(0 반환)하면 커밋하지 않음
            if page_inserted_count > 0:
                logger.info(f"페이지 {page} 작업 완료. 커밋을 준비합니다.")
                try:
                    self.repo.commit()
                    logger.info(f"페이지 {page} 커밋 완료.")
                    total_inserted_count += page_inserted_count
                except Exception as e:
                    logger.error(f"페이지 {page} 커밋 중 오류: {e}")
                    self.repo.rollback()
            else:
                logger.warning(f"페이지 {page} 삽입/발행 실패. 롤백을 수행합니다.")
                self.repo.rollback() # _save_and_publish가 실패했으므로 롤백

            logger.info("API 과호출 방지를 위해 1초 대기합니다.")
            time.sleep(1) # API 속도 조절

            page += 1

        # 모든 페이지 루프가 끝난 후
        logger.info(f"--- Processor '{fetcher_name}' 작업 완료 (총 {total_inserted_count}개 추가) ---")
        return total_inserted_count

    def _create_embeddings(self, dtos: List) -> List[Tuple]:
        """[Helper] 임베딩 생성 로직 (DTO 타입을 특정하지 않음)"""
        data_to_insert = []
        for dto in dtos:
            try:
                # DTO 객체가 스스로 임베딩 텍스트를 생성 (get_text_for_embedding 호출)
                embedding = self.embedder.create_embedding_for_service(dto)
                data_to_insert.append((dto, embedding))
                time.sleep(0.1) # Bedrock 속도 조절
            except ClientError as ce:
                logger.error(f"Bedrock API 오류: {ce}")
            except Exception as item_e:
                # DTO의 ID 속성 확인 (service_id 또는 job_id)
                item_id_str = getattr(dto, 'service_id', '알수없음')
                if hasattr(dto, 'get_composite_key'):
                    item_id_str = dto.get_composite_key() # Employment의 경우 복합 키 로깅

                logger.error(f"개별 DTO 임베딩 오류 (ID: {item_id_str}): {item_e}")
        return data_to_insert

    def _save_and_publish(self, data_list: List[Tuple]) -> int:
        """[Helper] DB 저장 및 SQS 발행 (트랜잭션) 로직 (DTO 타입을 특정하지 않음)"""
        logger.info(f"{len(data_list)}개의 임베딩 성공 건에 대해 DB 저장 및 SQS 발행을 시도합니다.")
        try:
            # repo가 DTO 리스트(Employment) 또는 count(Welfare)를 반환
            insert_result = self.repo.insert_services_batch(data_list)

            inserted_dtos = []
            inserted_count = 0

            if isinstance(insert_result, int):
                # WelfareRepository (count 반환)
                inserted_count = insert_result
                if inserted_count > 0:
                    # Welfare는 data_list가 곧 신규 목록임
                    inserted_dtos = [dto for dto, emb in data_list]
            elif isinstance(insert_result, list):
                # EmploymentRepository (필터링된 DTO 리스트 반환)
                inserted_dtos = insert_result
                inserted_count = len(inserted_dtos)

            #inserted_dtos는 이제 '진짜 신규' 목록만 포함
            if inserted_count > 0:
                self.publisher.publish_new_services(inserted_dtos)
                logger.info(f"신규 서비스 {inserted_count}개 DB 저장 및 SQS 발행 준비 완료.")
                # (중요) 커밋은 상위 메소드(run_for_fetcher)에서 수행
                return inserted_count
            else:
                logger.warning(f"DB 일괄 삽입 결과가 0건입니다 (모두 중복이거나 오류).")
                return 0

        except Exception as e:
            logger.error(f"DB/SQS 처리 중 오류: {e}. (롤백은 상위에서 수행)", exc_info=True)
            return 0
