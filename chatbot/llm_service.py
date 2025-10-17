# llm_service.py
import json
import boto3
import anthropic
import logging
from botocore.exceptions import ClientError
from config import config

logger = logging.getLogger()

# 클라이언트는 한 번만 초기화
bedrock_runtime = boto3.client(service_name='bedrock-runtime')
anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key) if config.anthropic_api_key else None

def get_embedding(text: str) -> list[float]:
    """텍스트를 Bedrock Titan 임베딩으로 변환합니다."""
    body = json.dumps({"inputText": text})
    try:
        response = bedrock_runtime.invoke_model(body=body, modelId='amazon.titan-embed-text-v2:0')
        response_body = json.loads(response.get('body').read())
        return response_body.get('embedding')
    except ClientError as e:
        logger.error(f"Bedrock 임베딩 생성 오류: {e}")
        raise

def get_anthropic_response(prompt: str) -> str:
    """Anthropic Claude API를 호출합니다."""
    if not anthropic_client:
        raise ConnectionError("Anthropic 클라이언트가 API 키 부족으로 초기화되지 않았습니다.")

    logger.info("Anthropic LLM을 호출합니다...")
    try:
        message = anthropic_client.messages.create(
            model='claude-3-5-sonnet-20240620',
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        ).content[0].text
        return message
    except Exception as e:
        logger.error(f"Anthropic API 호출 중 예외 발생: {e}")
        raise
