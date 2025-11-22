# chatbot/lambda_function.py
import logging
from mangum import Mangum
from main import app
from service import worker_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# FastAPI 핸들러 (API Gateway용)
mangum_handler = Mangum(app)

def lambda_handler(event, context):
    """
    Main Entry Point: 이벤트 소스에 따라 적절한 핸들러로 라우팅
    """

    # SQS 이벤트인지 감지
    # (Records 키가 있고, 첫 번째 레코드의 출처가 aws:sqs인 경우)
    if is_sqs_event(event):
        return worker_service.process_sqs_batch(event['Records'])

    # 기본 HTTP API 요청 (FastAPI)
    return mangum_handler(event, context)

def is_sqs_event(event):
    """이벤트가 SQS 트리거인지 확인하는 헬퍼 함수"""
    if 'Records' in event and isinstance(event['Records'], list) and len(event['Records']) > 0:
        if event['Records'][0].get('eventSource') == 'aws:sqs':
            return True
    return False
