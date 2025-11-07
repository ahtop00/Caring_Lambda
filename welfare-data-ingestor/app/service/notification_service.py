# -*- coding: utf-8 -*-
import json
import logging
from typing import List, TYPE_CHECKING
from dataclasses import asdict # DTO를 dict로 변환하기 위해 임포트
from botocore.exceptions import ClientError

# app 내부 모듈 임포트
try:
    from app.common_dto import CommonServiceDTO
except ImportError:
    # 로컬 테스트 등을 위한 예외 처리
    from ..common_dto import CommonServiceDTO


# Boto3 타입 힌트를 위한 설정
if TYPE_CHECKING:
    from mypy_boto3_sqs.client import SQSClient
else:
    SQSClient = object

logger = logging.getLogger()

class NotificationService:
    """
    신규 복지 서비스 데이터를 SQS 큐로 발행하는 서비스
    """

    # SQS send_message_batch API의 최대 배치 크기
    MAX_BATCH_SIZE = 10

    def __init__(self, sqs_client: SQSClient, queue_url: str):
        """
        서비스 초기화
        :param sqs_client: Boto3 SQS 클라이언트
        :param queue_url: 발행할 SQS 큐의 URL (config에서 주입)
        """
        if not queue_url:
            msg = "FATAL: SQS_QUEUE_URL이(가) 설정되지 않았습니다."
            logger.error(msg)
            raise ValueError(msg)

        self.sqs = sqs_client
        self.queue_url = queue_url

    def publish_new_services(self, dtos: List[CommonServiceDTO]):
        """
        신규 서비스 DTO 리스트를 SQS 큐에 일괄 발행합니다.
        (10개 이상일 경우 자동으로 분할하여 발행)

        :param dtos: 발행할 CommonServiceDTO 객체 리스트
        """
        if not dtos:
            logger.info("SQS에 발행할 신규 서비스가 없습니다.")
            return

        logger.info(f"총 {len(dtos)}개의 신규 서비스를 SQS 큐에 발행 시작...")

        # SQS `send_message_batch`는 최대 10개씩만 보낼 수 있으므로
        # 리스트를 10개씩 분할(chunk)하여 처리합니다.
        for i in range(0, len(dtos), self.MAX_BATCH_SIZE):

            chunk = dtos[i:i + self.MAX_BATCH_SIZE]
            entries = []

            for dto in chunk:
                try:
                    # DTO 객체를 JSON 직렬화가 가능한 dict로 변환
                    dto_dict = asdict(dto)

                    # SQS 메시지 본문은 문자열이어야 함 (JSON 문자열)
                    message_body = json.dumps(dto_dict, ensure_ascii=False)

                    # SQS 배치 항목 생성
                    entries.append({
                        'Id': dto.service_id, # 각 메시지의 고유 ID (service_id 사용)
                        'MessageBody': message_body
                        # (참고: 큐가 FIFO(.fifo)가 아니므로 MessageGroupId 불필요)
                    })
                except Exception as e:
                    logger.error(f"SQS 메시지(ID: {dto.service_id}) 생성 중 직렬화 오류: {e}")

            if not entries:
                logger.warning(f"배치 {i//self.MAX_BATCH_SIZE + 1}: 직렬화에 성공한 메시지가 없습니다.")
                continue

            # SQS API 호출
            try:
                logger.info(f"SQS에 {len(entries)}개 메시지 일괄 발행 시도...")
                response = self.sqs.send_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )

                # [중요] 일괄 발행 실패 시 예외 처리
                if response.get('Failed'):
                    logger.error(f"SQS 일괄 발행 실패: {response['Failed']}")
                    # 실패 시 DB 트랜잭션 롤백을 위해 예외 발생
                    raise Exception(f"SQS 일부 메시지 발행 실패: {response['Failed']}")

                logger.info(f"SQS 발행 성공 (Batch {i//self.MAX_BATCH_SIZE + 1})")

            except ClientError as ce:
                logger.error(f"SQS 메시지 일괄 발행 중 Boto3 오류: {ce}")
                raise ce # DB 롤백을 위해 예외를 상위로 전파
            except Exception as e:
                logger.error(f"SQS 메시지 일괄 발행 중 알 수 없는 오류: {e}")
                raise e # DB 롤백을 위해 예외를 상위로 전파
