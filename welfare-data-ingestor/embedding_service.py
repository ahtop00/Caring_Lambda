# -*- coding: utf-8 -*-
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()

class EmbeddingService:
    """Amazon Bedrock을 이용한 텍스트 임베딩 생성을 담당하는 클래스"""

    def __init__(self, bedrock_runtime, model_id):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = model_id
        if not self.model_id:
            raise ValueError("Bedrock 모델 ID가 설정되지 않았습니다.")

    def _build_embedding_text(self, service_item):
        """임베딩을 생성할 원본 텍스트를 조합합니다."""

        # .get(key, '') 대신 .get(key) or '대체텍스트' 사용
        ctpvNm = service_item.get('ctpvNm') or ''
        sggNm = service_item.get('sggNm') or ''
        trgterIndvdlNmArray = service_item.get('trgterIndvdlNmArray') or '정보 없음'
        sprtCycNm = service_item.get('sprtCycNm') or '정보 없음'
        srvPvsnNm = service_item.get('srvPvsnNm') or '정보 없음'
        aplyMtdNm = service_item.get('aplyMtdNm') or '정보 없음'
        servNm = service_item.get('servNm') or '제목 없음'
        servDgst = service_item.get('servDgst') or '내용 없음'

        return (
            f"이 복지 서비스는 {ctpvNm} {sggNm} 지역의 {trgterIndvdlNmArray}를 대상으로 합니다. "
            f"지원 주기는 {sprtCycNm}이며, {srvPvsnNm} 형태로 제공됩니다. "
            f"신청은 {aplyMtdNm} 방식으로 할 수 있습니다. "
            f"서비스명은 '{servNm}'이고, 주요 내용은 다음과 같습니다: {servDgst}"
        )

    def get_embedding(self, text):
        """주어진 텍스트를 Bedrock API를 통해 벡터로 변환합니다."""
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

    def create_embedding_for_service(self, service_item):
        """복지 서비스 데이터(dict)를 받아 임베딩을 생성합니다."""
        text_to_embed = self._build_embedding_text(service_item)
        return self.get_embedding(text_to_embed)
