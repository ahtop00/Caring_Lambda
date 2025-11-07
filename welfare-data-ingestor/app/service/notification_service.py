# -*- coding: utf-8 -*-
import json
import logging
from typing import List, TYPE_CHECKING, Any
from dataclasses import asdict
from botocore.exceptions import ClientError
import uuid

try:
    from app.dto.common_dto import CommonServiceDTO
    from app.dto.employment_dto import JobOpeningDTO
except ImportError:
    pass

if TYPE_CHECKING:
    from mypy_boto3_sqs.client import SQSClient
else:
    SQSClient = object

logger = logging.getLogger()

class NotificationService:
    """
    신규 서비스 데이터를 SQS 큐로 발행하는 서비스
    """
    MAX_BATCH_SIZE = 10

    def __init__(self, sqs_client: SQSClient, queue_url: str):
        if not queue_url:
            msg = "FATAL: SQS_QUEUE_URL이(가) 설정되지 않았습니다."
            logger.error(msg)
            raise ValueError(msg)
        self.sqs = sqs_client
        self.queue_url = queue_url

    def publish_new_services(self, dtos: List[Any]):
        """
        신규 DTO(CommonServiceDTO 또는 JobOpeningDTO) 리스트를
        SQS 큐에 일괄 발행합니다.
        """
        if not dtos:
            logger.info("SQS에 발행할 신규 서비스가 없습니다.")
            return

        logger.info(f"총 {len(dtos)}개의 신규 서비스를 SQS 큐에 발행 시작...")

        for i in range(0, len(dtos), self.MAX_BATCH_SIZE):
            chunk = dtos[i:i + self.MAX_BATCH_SIZE]
            entries = []

            for dto in chunk:
                try:
                    dto_dict = asdict(dto)
                    message_body = json.dumps(dto_dict, ensure_ascii=False)

                    # [수정] DTO 타입에 따라 SQS Batch ID를 동적으로 할당
                    # JobOpeningDTO는 DB 저장 전이라 ID가 없으므로 UUID 사용
                    # CommonServiceDTO는 service_id를 사용
                    sqs_id = getattr(dto, 'service_id', None)
                    if not sqs_id:
                        # JobOpeningDTO거나 service_id가 없는 경우
                        sqs_id = str(uuid.uuid4())

                    entries.append({
                        'Id': sqs_id.replace(" ", "_"), # SQS ID는 공백 불가
                        'MessageBody': message_body
                    })
                except Exception as e:
                    item_id_str = getattr(dto, 'service_id', 'N/A')
                    logger.error(f"SQS 메시지(ID: {item_id_str}) 생성 중 직렬화 오류: {e}")

            if not entries:
                logger.warning(f"배치 {i//self.MAX_BATCH_SIZE + 1}: 직렬화에 성공한 메시지가 없습니다.")
                continue

            try:
                logger.info(f"SQS에 {len(entries)}개 메시지 일괄 발행 시도...")
                response = self.sqs.send_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )
                if response.get('Failed'):
                    logger.error(f"SQS 일괄 발행 실패: {response['Failed']}")
                    raise Exception(f"SQS 일부 메시지 발행 실패: {response['Failed']}")
                logger.info(f"SQS 발행 성공 (Batch {i//self.MAX_BATCH_SIZE + 1})")
            except ClientError as ce:
                logger.error(f"SQS 메시지 일괄 발행 중 Boto3 오류: {ce}")
                raise ce
            except Exception as e:
                logger.error(f"SQS 메시지 일괄 발행 중 알 수 없는 오류: {e}")
                raise e
