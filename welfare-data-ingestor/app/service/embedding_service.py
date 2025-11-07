# -*- coding: utf-8 -*-
import json
import logging
from botocore.exceptions import ClientError
from typing import TYPE_CHECKING, List, Any

# [수정] DTO 임포트 로직 제거 (타입에 의존하지 않음)

# 타입 힌트를 위한 설정
if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

logger = logging.getLogger()

class EmbeddingService:
    """Amazon Bedrock을 이용한 텍스트 임베딩 생성을 담당하는 클래스"""

    def __init__(self, bedrock_runtime: 'BedrockRuntimeClient', model_id: str):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = model_id
        if not self.model_id:
            raise ValueError("Bedrock 모델 ID가 설정되지 않았습니다.")

    def _build_embedding_text(self, service_dto: Any) -> str:
        """
        [수정]
        DTO 객체가 'get_text_for_embedding' 메소드를 가지고 있다고 가정 (Duck Typing)
        """
        if not hasattr(service_dto, 'get_text_for_embedding'):
            raise TypeError(f"객체 {type(service_dto)}에 'get_text_for_embedding' 메소드가 없습니다.")

        return service_dto.get_text_for_embedding()

    def get_embedding(self, text: str) -> List[float]:
        # ... (기존 로직과 동일) ...
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
            raise e
        except Exception as e:
            logger.error(f"임베딩 응답 처리 중 오류: {e}")
            raise e

    def create_embedding_for_service(self, service_dto: Any) -> List[float]:
        """
        다양한 DTO 객체(CommonServiceDTO, JobOpeningDTO 등)를 받아 임베딩을 생성합니다.
        :param service_dto: 'get_text_for_embedding' 메소드를 가진 객체
        :return: 임베딩 벡터 (float 리스트)
        """
        text_to_embed = self._build_embedding_text(service_dto)
        return self.get_embedding(text_to_embed)
