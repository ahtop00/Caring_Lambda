# lambda_function.py
# -*- coding: utf-8 -*-
import json
import logging
import boto3

from app import config
from app.factory import get_dependencies, get_sources_to_run
from app.processor import IngestProcessor
from app.service.embedding_service import EmbeddingService
from app.service.notification_service import NotificationService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- 전역 모듈 초기화 (Boto3 클라이언트, 공통 서비스) ---
# (Warm Start 시 재사용)
try:
    bedrock_runtime_client = boto3.client(service_name='bedrock-runtime')
    sqs_client = boto3.client(service_name='sqs')

    embedder = EmbeddingService(
        bedrock_runtime=bedrock_runtime_client,
        model_id=config.BEDROCK_MODEL_ID
    )
    publisher = NotificationService(
        sqs_client=sqs_client,
        queue_url=config.SQS_QUEUE_URL
    )
    logger.info("공통 서비스 (Embedder, Publisher) 초기화 완료.")

except Exception as e:
    logger.error(f"FATAL: 전역 모듈 초기화 실패: {e}")
    raise e

def handler(event, context):
    """
    AWS Lambda 메인 핸들러.
    [역할] 이벤트 파싱 -> Factory로 의존성 요청 -> Processor 실행
    """
    logger.info(f"이벤트 수신: {event}")

    # 1. 실행할 소스 결정 (라우팅)
    try:
        sources = get_sources_to_run(event)
    except ValueError as e:
        logger.error(str(e))
        return {'statusCode': 400, 'body': json.dumps(str(e))}

    total_inserted_count = 0

    # 소스별로 루프 실행
    for source in sources:
        repo = None # [중요] repo는 소스마다 다를 수 있으므로 루프 내에서 생성/종료
        try:
            # Factory에서 의존성(Fetcher, Repo, Config) 가져오기
            logger.info(f"Source '{source}'에 대한 의존성 주입 시작...")
            deps = get_dependencies(source, config.DB_CONFIG)

            repo = deps["repository"]
            fetcher = deps["fetcher"]
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
            if repo: repo.rollback() # Processor에서 놓친 오류가 있더라도 롤백
            # (오류가 나도 다음 source는 계속 진행)

        finally:
            # 한 소스의 작업이 끝나면 반드시 DB 연결 종료
            if repo: repo.close()
            logger.info(f"Source '{source}' 작업 완료. DB 연결 종료.")

    logger.info(f"## Lambda 실행 종료 (총 {total_inserted_count}개 추가) ##")
    return {
        'statusCode': 200,
        'body': json.dumps(f"성공적으로 총 {total_inserted_count}개의 신규 서비스를 처리했습니다.")
    }
