# app/processor.py
# -*- coding: utf-8 -*-
import logging
import time
from typing import List, Tuple
from botocore.exceptions import ClientError

# app 내부 모듈 임포트
from app.fetchers.base_fetcher import BaseWelfareFetcher
from app.repository.base_repository import BaseRepository # (타입 힌트용)
from app.service.embedding_service import EmbeddingService
from app.service.notification_service import NotificationService
from app.common_dto import CommonServiceDTO

logger = logging.getLogger()

class IngestProcessor:
    """
    데이터 수집/처리/저장의 핵심 비즈니스 로직(Orchestration)을 담당.
    (lambda_function.py의 172줄짜리 코드가 여기로 이동)
    """

    def __init__(self,
                 repo: BaseRepository, # (중요) WelfareRepository가 아닌 부모 타입으로 받음
                 embedder: EmbeddingService,
                 publisher: NotificationService,
                 page_config: dict):
        """
        필요한 의존성을 외부에서 주입받습니다.
        """
        self.repo = repo
        self.embedder = embedder
        self.publisher = publisher
        self.start_page = page_config.get('start_page', 1)
        self.page_limit = page_config.get('page_limit', 5)

    def run_for_fetcher(self, fetcher: BaseWelfareFetcher, event_params: dict):
        """
        주입된 단일 Fetcher에 대해 수집 작업을 실행합니다.
        (lambda_function.py의 'for fetcher in ...' 루프 내부 로직)
        """
        fetcher_name = fetcher.__class__.__name__
        logger.info(f"--- Processor '{fetcher_name}' 작업 시작 ---")

        total_inserted_count = 0
        end_page = self.start_page + self.page_limit

        for page in range(self.start_page, end_page):
            logger.info(f"--- API 페이지 {page}/{end_page - 1} 조회 시작 ({fetcher_name}) ---")

            # 1. Fetch
            service_dtos: List[CommonServiceDTO] = fetcher.fetch_services_by_page(page, event_params)
            if not service_dtos:
                logger.info(f"페이지 {page}에서 더 이상 조회된 서비스가 없어 '{fetcher_name}' 작업을 중단합니다.")
                break

            # 2. Filter
            ids_from_api = [dto.service_id for dto in service_dtos if dto.service_id]
            if not ids_from_api: continue # 유효 ID 없음

            existing_ids = self.repo.get_existing_ids(ids_from_api)
            new_service_dtos = [dto for dto in service_dtos if dto.service_id not in existing_ids]
            if not new_service_dtos:
                logger.info(f"페이지 {page}에는 신규 서비스가 없습니다.")
                continue

            # 3. Embed
            logger.info(f"페이지 {page}에서 {len(new_service_dtos)}개의 신규 서비스를 발견했습니다. 임베딩을 시작합니다.")
            data_to_insert: List[Tuple[CommonServiceDTO, List[float]]] = self._create_embeddings(new_service_dtos)
            if not data_to_insert:
                logger.info("임베딩에 성공한 데이터가 없습니다.")
                continue

            # 4. Save & Publish (트랜잭션)
            page_inserted_count = self._save_and_publish(data_to_insert)
            total_inserted_count += page_inserted_count

            logger.info("API 과호출 방지를 위해 1초 대기합니다.")
            time.sleep(1) # API 속도 조절

        return total_inserted_count

    def _create_embeddings(self, dtos: List[CommonServiceDTO]) -> List[Tuple[CommonServiceDTO, List[float]]]:
        """[Helper] 임베딩 생성 로직 분리"""
        data_to_insert = []
        for dto in dtos:
            try:
                embedding = self.embedder.create_embedding_for_service(dto)
                data_to_insert.append((dto, embedding))
                time.sleep(0.1) # Bedrock API 속도 조절
            except ClientError as ce:
                logger.error(f"Bedrock API 오류 (ServiceId: {dto.service_id}): {ce}")
            except Exception as item_e:
                logger.error(f"개별 DTO 임베딩 오류 (ServiceId: {dto.service_id}): {item_e}")
        return data_to_insert

    def _save_and_publish(self, data_list: List[Tuple[CommonServiceDTO, List[float]]]) -> int:
        """[Helper] DB 저장 및 SQS 발행 (트랜잭션) 로직 분리"""
        logger.info(f"{len(data_list)}개의 임베딩 성공 건에 대해 DB 저장 및 SQS 발행을 시도합니다.")
        try:
            # (중요) repo가 welfare_repo인지 employment_repo인지 몰라도
            # 'insert_services_batch' (또는 공통 인터페이스)를 호출
            inserted_count = self.repo.insert_services_batch(data_list)

            if inserted_count > 0:
                inserted_dtos = [dto for dto, emb in data_list]
                self.publisher.publish_new_services(inserted_dtos)

                # [중요] Processor는 commit/rollback을 직접 호출
                self.repo.commit()

                logger.info(f"신규 서비스 {inserted_count}개 DB 저장 및 SQS 발행 완료.")
                return inserted_count
            else:
                logger.warning(f"DB 일괄 삽입 결과가 0건입니다 (롤백됨).")
                return 0

        except Exception as e:
            logger.error(f"DB/SQS 처리 중 오류: {e}. 트랜잭션을 롤백합니다.", exc_info=True)
            self.repo.rollback() # 발행 실패 시 DB 삽입도 롤백
            return 0
