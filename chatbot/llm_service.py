# llm_service.py
import json
import boto3
import anthropic
import logging
from botocore.exceptions import ClientError
from config import config

logger = logging.getLogger()

# --- 클라이언트 초기화 (한 번만 실행) ---
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

# --- 내부 호출 함수들 (private) ---

def _get_bedrock_response(prompt: str) -> str:
    """[내부 함수] AWS Bedrock을 통해 Claude 모델을 호출합니다."""
    logger.info("Bedrock Claude 모델을 호출합니다.")
    model_id = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except ClientError as e:
        logger.error(f"Bedrock API 호출 중 예외 발생: {e}")
        raise

def _get_anthropic_direct_response(prompt: str) -> str:
    """[내부 함수] Anthropic API를 직접 호출합니다."""
    if not anthropic_client:
        raise ConnectionError("Anthropic 클라이언트가 API 키 부족으로 초기화되지 않았습니다.")

    logger.info("Anthropic API를 직접 호출합니다.")
    try:
        message = anthropic_client.messages.create(
            model='claude-3-5-sonnet-20240620',
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        ).content[0].text
        return message
    except Exception as e:
        logger.error(f"Anthropic API 직접 호출 중 예외 발생: {e}")
        raise

# --- 메인 호출 함수 (public) ---

def get_llm_response(prompt: str, use_bedrock: bool = False) -> str:
    """
    use_bedrock 플래그 값에 따라 적절한 LLM 서비스를 선택하여 호출합니다.

    :param prompt: LLM에 전달할 프롬프트 문자열
    :param use_bedrock: True이면 Bedrock, False이면 Anthropic 직접 API를 사용
    :return: LLM의 응답 문자열
    """
    if use_bedrock:
        return _get_bedrock_response(prompt)
    else:
        return _get_anthropic_direct_response(prompt)
