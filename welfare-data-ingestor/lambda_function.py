# -*- coding: utf-8 -*-
import json
import logging
import time

import boto3
from botocore.exceptions import ClientError

import config
from api_fetcher import ApiFetcher
from embedding_service import EmbeddingService
from repository import WelfareRepository

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    bedrock_runtime_client = boto3.client(service_name='bedrock-runtime')

    fetcher = ApiFetcher(
        api_endpoint=config.API_ENDPOINT,
        service_key=config.SERVICE_KEY,
        rows_per_page=config.ROWS_PER_PAGE
    )

    embedder = EmbeddingService(
        bedrock_runtime=bedrock_runtime_client,
        model_id=config.BEDROCK_MODEL_ID
    )
    logger.info("필수 서비스 모듈(Fetcher, Embedder) 초기화 완료.")

except Exception as e:
    logger.error(f"FATAL: 전역 모듈 초기화 실패: {e}")
    raise e


def handler(event, context):
    """
    AWS Lambda 메인 핸들러
    1. API를 호출하여 복지 서비스 데이터를 가져옵니다.
    2. DB에서 기존 데이터를 조회하여 신규 서비스만 필터링합니다.
    3. 신규 서비스의 텍스트를 Bedrock을 통해 임베딩합니다.
    4. 신규 서비스와 임베딩을 DB에 저장합니다.
    """
    logger.info(f"## Lambda 실행 시작 (시작 페이지: {config.START_PAGE}, 페이지 제한: {config.PAGE_LIMIT}) ##")

    total_inserted_count = 0
    repo = None  # DB 커넥션은 핸들러 내에서 생성/종료

    try:
        # 1. 리포지토리(DB) 초기화 (매 실행 시마다 새 연결)
        repo = WelfareRepository(config.DB_CONFIG)

        end_page = config.START_PAGE + config.PAGE_LIMIT
        for page in range(config.START_PAGE, end_page):
            logger.info(f"--- API 페이지 {page}/{end_page - 1} 조회 시작 ---")

            # 2. (Fetcher) API로부터 서비스 조회
            services_from_api = fetcher.fetch_services_by_page(page, event)
            if not services_from_api:
                logger.info(f"페이지 {page}에서 더 이상 조회된 서비스가 없어 전체 작업을 중단합니다.")
                break

            logger.info(f"페이지 {page}에서 {len(services_from_api)}개의 서비스를 API로부터 수신했습니다.")

            # 3. (Repository) 기존 ID 조회 및 신규 서비스 필터링
            ids_from_api = [s.get('servId') for s in services_from_api if s.get('servId')]
            if not ids_from_api:
                logger.info(f"페이지 {page}에 유효한 ID가 없습니다. 다음 페이지로 넘어갑니다.")
                continue

            existing_ids = repo.get_existing_ids(ids_from_api)
            new_services = [s for s in services_from_api if s.get('servId') not in existing_ids]

            if not new_services:
                logger.info(f"페이지 {page}에는 신규 서비스가 없습니다. 다음 페이지로 넘어갑니다.")
                continue

            # 4. (Embedder & Repository) 신규 서비스 처리
            logger.info(f"페이지 {page}에서 {len(new_services)}개의 신규 서비스를 발견했습니다. 임베딩 및 DB 저장을 시작합니다.")
            page_inserted_count = 0
            for service in new_services:
                try:
                    # 4-1. (Embedder) 임베딩 생성
                    embedding = embedder.create_embedding_for_service(service)

                    # 4-2. (Repository) DB 저장
                    repo.insert_service(service, embedding)
                    page_inserted_count += 1

                    # Bedrock API 속도 조절 (필요시)
                    time.sleep(0.1)

                except ClientError as ce:
                    logger.error(f"Bedrock API 오류 (ServiceId: {service.get('servId')}): {ce}")
                    # 개별 서비스 임베딩 실패 시, 다음 서비스로 계속 진행
                except Exception as item_e:
                    logger.error(f"개별 서비스 처리 오류 (ServiceId: {service.get('servId')}): {item_e}")
                    # 개별 서비스 DB 저장 실패 시, 롤백하지 않고 다음으로 넘어감 (선택적)

            # 5. (Repository) 페이지 단위 커밋
            if page_inserted_count > 0:
                repo.commit()
                logger.info(f"페이지 {page}의 신규 서비스 {page_inserted_count}개 항목을 DB에 커밋했습니다.")
            total_inserted_count += page_inserted_count

            logger.info("API 과호출 방지를 위해 1초 대기합니다.")
            time.sleep(1)

        logger.info(f"총 {total_inserted_count}개의 신규 레코드를 성공적으로 추가했습니다.")
        return {'statusCode': 200, 'body': json.dumps(f"성공적으로 총 {total_inserted_count}개의 신규 서비스를 처리했습니다.")}

    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        if repo: repo.rollback()
        raise e

    finally:
        if repo: repo.close()
        logger.info("## Lambda 실행 종료 ##")
