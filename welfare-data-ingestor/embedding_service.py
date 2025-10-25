# -*- coding: utf-8 -*-
import json
import logging
from botocore.exceptions import ClientError
from typing import TYPE_CHECKING

try:
    from common_dto import CommonServiceDTO
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common_dto import CommonServiceDTO

# 타입 힌트를 위한 설정
if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

logger = logging.getLogger()

class EmbeddingService:
    """Amazon Bedrock을 이용한 텍스트 임베딩 생성을 담당하는 클래스"""

    def __init__(self, bedrock_runtime: 'BedrockRuntimeClient', model_id: str):
        """
        EmbeddingService를 초기화합니다.

        :param bedrock_runtime: Boto3 Bedrock 런타임 클라이언트
        :param model_id: 사용할 Bedrock 임베딩 모델 ID
        """
        self.bedrock_runtime = bedrock_runtime
        self.model_id = model_id
        if not self.model_id:
            raise ValueError("Bedrock 모델 ID가 설정되지 않았습니다.")

    def _build_embedding_text(self, service_dto: CommonServiceDTO) -> str:
        """
        임베딩을 생성할 원본 텍스트를 DTO로부터 가져옵니다.
        (복잡한 텍스트 조합 로직이 DTO 내부로 캡슐화됨)
        """
        return service_dto.get_text_for_embedding()

    def get_embedding(self, text: str) -> List[float]:
        """주어진 텍스트를 Bedrock API를 통해 벡터(float 리스트)로 변환합니다."""
        body = json.dumps({"inputText": text})

        try:
            response = self.bedrock_runtime.invoke_model(
                body=body,
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )
            response_body = json.loads(response.get('body').read())
            embedding = response_body.get('embedding')

            if not embedding:
                logger.error(f"Bedrock 응답에 'embedding' 키가 없습니다. 응답: {response_body}")
                raise ValueError("임베딩 생성 실패: 응답 없음")

            return embedding

        except ClientError as e:
            logger.error(f"Bedrock API 호출 중 오류 발생: {e}")
            raise e # 오류를 다시 발생시켜 상위 핸들러가 처리하도록 함
        except Exception as e:
            logger.error(f"임베딩 응답 처리 중 오류: {e}")
            raise e

    def create_embedding_for_service(self, service_dto: CommonServiceDTO) -> List[float]:
        """
        복지 서비스 DTO(CommonServiceDTO)를 받아 임베딩을 생성합니다.

        :param service_dto: 표준화된 복지 서비스 DTO 객체
        :return: 임베딩 벡터 (float 리스트)
        """
        # DTO로부터 표준화된 텍스트 가져오기
        text_to_embed = self._build_embedding_text(service_dto)

        # Bedrock API 호출
        return self.get_embedding(text_to_embed)
