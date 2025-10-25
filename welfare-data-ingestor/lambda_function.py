# -*- coding: utf-8 -*-
import json
import logging
import time
from typing import List

import boto3
from botocore.exceptions import ClientError

import config  # 'LOCAL_', 'CENTRAL_' 변수가 포함된 새 config
# 'fetchers/' 폴더에서 두 Fetcher를 모두 임포트
from fetchers.local_fetcher import LocalWelfareFetcher
from fetchers.central_fetcher import CentralWelfareFetcher
from embedding_service import EmbeddingService
from repository import WelfareRepository
from common_dto import CommonServiceDTO

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    bedrock_runtime_client = boto3.client(service_name='bedrock-runtime')

    embedder = EmbeddingService(
        bedrock_runtime=bedrock_runtime_client,
        model_id=config.BEDROCK_MODEL_ID
    )

    fetchers = {
        "local": LocalWelfareFetcher(
            api_endpoint=config.LOCAL_API_ENDPOINT,
            service_key=config.LOCAL_API_KEY,
            rows_per_page=config.LOCAL_ROWS_PER_PAGE
        ),
        "central": CentralWelfareFetcher(
            api_endpoint=config.CENTRAL_API_ENDPOINT,
            service_key=config.CENTRAL_API_KEY,
            rows_per_page=config.CENTRAL_ROWS_PER_PAGE
        )
    }

    logger.info(f"필수 모듈(Embedder, Fetcher {len(fetchers)}개) 초기화 완료.")

except Exception as e:
    logger.error(f"FATAL: 전역 모듈 초기화 실패: {e}")
    raise e


def handler(event, context):
    """
    AWS Lambda 메인 핸들러 (라우터)
    event에 포함된 'source' 파라미터에 따라 적절한 Fetcher를 실행합니다.
    - {"source": "local"}   -> LocalWelfareFetcher 실행
    - {"source": "central"} -> CentralWelfareFetcher 실행
    - {} (파라미터 없음)     -> 모든 Fetcher를 순차 실행 (테스트용)
    """

    # 'source' 파라미터 확인
    source_to_run = event.get("source")

    fetcher_list_to_run = []

    if source_to_run:
        if source_to_run in fetchers:
            # "local" 또는 "central"이 명시된 경우
            logger.info(f"## 'source: {source_to_run}' 파라미터 감지, 해당 Fetcher만 실행 ##")
            fetcher_list_to_run.append(fetchers[source_to_run])
        else:
            # "source"가 왔는데 모르는 값이면 에러 처리
            logger.error(f"알 수 없는 'source' 값입니다: {source_to_run}")
            return {'statusCode': 400, 'body': 'Invalid source parameter'}
    else:
        # 파라미터가 없으면 모든 Fetcher를 순차 실행 (안전한 기본값)
        logger.info(f"## 'source' 파라미터 없음, 정의된 모든 Fetcher 순차 실행 ##")
        fetcher_list_to_run = list(fetchers.values())


    total_inserted_count = 0
    repo = None

    try:
        repo = WelfareRepository(config.DB_CONFIG)

        for fetcher in fetcher_list_to_run:
            fetcher_name = fetcher.__class__.__name__
            logger.info(f"--- Fetcher '{fetcher_name}' 작업 시작 ---")

            # 각 Fetcher에 맞는 설정값(페이지)을 config에서 가져오기
            if "Local" in fetcher_name:
                start_page = config.LOCAL_START_PAGE
                page_limit = config.LOCAL_PAGE_LIMIT
            elif "Central" in fetcher_name:
                start_page = config.CENTRAL_START_PAGE
                page_limit = config.CENTRAL_PAGE_LIMIT
            else:
                # 기본값
                start_page = 1
                page_limit = 5

            end_page = start_page + page_limit
            for page in range(start_page, end_page):
                logger.info(f"--- API 페이지 {page}/{end_page - 1} 조회 시작 ({fetcher_name}) ---")

                # (Fetcher) API -> DTO 리스트 조회
                # 'event'를 그대로 넘겨주면, 'searchWrd' 같은 추가 파라미터도 전달 가능
                service_dtos: List[CommonServiceDTO] = fetcher.fetch_services_by_page(page, event)

                if not service_dtos:
                    logger.info(f"페이지 {page}에서 더 이상 조회된 서비스가 없어 '{fetcher_name}' 작업을 중단합니다.")
                    break

                logger.info(f"페이지 {page}에서 {len(service_dtos)}개의 DTO를 API로부터 수신했습니다.")

                # (Repository) 기존 ID 조회 및 DTO 필터링
                ids_from_api = [dto.service_id for dto in service_dtos if dto.service_id]
                if not ids_from_api:
                    logger.info(f"페이지 {page}에 유효한 ID가 없습니다. 다음 페이지로 넘어갑니다.")
                    continue

                existing_ids = repo.get_existing_ids(ids_from_api)

                # DTO 리스트 필터링
                new_service_dtos = [dto for dto in service_dtos if dto.service_id not in existing_ids]

                if not new_service_dtos:
                    logger.info(f"페이지 {page}에는 신규 서비스가 없습니다. 다음 페이지로 넘어갑니다.")
                    continue

                # (Embedder & Repository) 신규 DTO 처리
                logger.info(f"페이지 {page}에서 {len(new_service_dtos)}개의 신규 서비스를 발견했습니다. 임베딩 및 DB 저장을 시작합니다.")
                page_inserted_count = 0
                for dto in new_service_dtos:
                    try:
                        # Embedder에 DTO 전달
                        embedding = embedder.create_embedding_for_service(dto)

                        # Repository에 DTO 전달
                        repo.insert_service(dto, embedding)
                        page_inserted_count += 1
                        time.sleep(0.1) # Bedrock API 속도 조절

                    except ClientError as ce:
                        logger.error(f"Bedrock API 오류 (ServiceId: {dto.service_id}): {ce}")
                    except Exception as item_e:
                        logger.error(f"개별 DTO 처리 오류 (ServiceId: {dto.service_id}): {item_e}")

                # (Repository) 페이지 단위 커밋
                if page_inserted_count > 0:
                    repo.commit()
                    logger.info(f"페이지 {page} ({fetcher_name}) 신규 서비스 {page_inserted_count}개 커밋 완료.")
                total_inserted_count += page_inserted_count

                logger.info("API 과호출 방지를 위해 1초 대기합니다.")
                time.sleep(1) # API 속도 조절

    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        if repo: repo.rollback()
        raise e

    finally:
        if repo: repo.close()
        logger.info(f"## Lambda 실행 종료 (총 {total_inserted_count}개 추가) ##")

    return {'statusCode': 200, 'body': json.dumps(f"성공적으로 총 {total_inserted_count}개의 신규 서비스를 처리했습니다.")}
