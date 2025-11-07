# -*- coding: utf-8 -*-
import json
import logging
import boto3

from app import config
from app.factory import get_dependencies, get_sources_to_run
from app.processor import IngestProcessor
from app.service.embedding_service import EmbeddingService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- 전역 모듈 초기화 (Boto3 클라이언트, 공통 서비스) ---
try:
    bedrock_runtime_client = boto3.client(service_name='bedrock-runtime')
    sqs_client = boto3.client(service_name='sqs')

    # 공통 서비스 (모든 Processor가 공유)
    embedder = EmbeddingService(
        bedrock_runtime=bedrock_runtime_client,
        model_id=config.BEDROCK_MODEL_ID
    )

    logger.info("공통 서비스 (Embedder, Boto3 Clients) 초기화 완료.")

except Exception as e:
    logger.error(f"FATAL: 전역 모듈 초기화 실패: {e}")
    raise e

def handler(event, context):
    """
    AWS Lambda 메인 핸들러.
    [역할] 이벤트 파싱 -> Factory로 의존성 요청 -> Processor 실행
    """
    logger.info(f"이벤트 수신: {event}")

    try:
        sources = get_sources_to_run(event)
    except ValueError as e:
        logger.error(str(e))
        return {'statusCode': 400, 'body': json.dumps(str(e))}

    total_inserted_count = 0

    for source in sources:
        repo = None
        try:
            logger.info(f"Source '{source}'에 대한 의존성 주입 시작...")

            # Factory에 sqs_client 주입
            deps = get_dependencies(source, config.DB_CONFIG, sqs_client)

            repo = deps["repository"]
            fetcher = deps["fetcher"]
            publisher = deps["publisher"]
            page_config = deps["page_config"]

            # Processor 생성 (의존성 주입)
            processor = IngestProcessor(
                repo=repo,
                embedder=embedder,
                publisher=publisher,
                page_config=page_config
            )

            # 실행
            count = processor.run_for_fetcher(fetcher, event_params=event)
            total_inserted_count += count

        except Exception as e:
            logger.error(f"Source '{source}' 처리 중 핸들러 레벨 오류: {e}", exc_info=True)
            if repo: repo.rollback()

        finally:
            if repo: repo.close()
            logger.info(f"Source '{source}' 작업 완료. DB 연결 종료.")

    logger.info(f"## Lambda 실행 종료 (총 {total_inserted_count}개 추가) ##")
    return {
        'statusCode': 200,
        'body': json.dumps(f"성공적으로 총 {total_inserted_count}개의 신규 서비스를 처리했습니다.")
    }
