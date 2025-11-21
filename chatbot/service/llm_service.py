import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

try:
    from config import config
except ImportError:
    from ..config import config

# Optional: Vertex AI (Gemini) 라이브러리
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from google.oauth2 import service_account
except ImportError:
    print("Warning: 'google-cloud-aiplatform' 또는 'google-auth'가 설치되지 않았습니다. Gemini를 사용할 수 없습니다.")
    vertexai = None
    GenerativeModel = None
    service_account = None

logger = logging.getLogger()

# --- 상수 설정 (모델 ID 관리) ---
MODEL_ID_BEDROCK_CLAUDE = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
MODEL_ID_BEDROCK_EMBEDDING = 'amazon.titan-embed-text-v2:0'
MODEL_ID_GEMINI = "gemini-2.5-pro"

# --- 클라이언트 초기화 ---
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='ap-northeast-2')

# Vertex AI (Gemini) 초기화 로직
gemini_pro_model = None

if vertexai and service_account:
    try:
        gcp_ssm_name = config.gcp_ssm_param_name
        if gcp_ssm_name:
            # SSM에서 GCP 자격 증명 가져오기
            ssm_client = boto3.client('ssm', region_name='ap-northeast-2')
            ssm_response = ssm_client.get_parameter(
                Name=gcp_ssm_name,
                WithDecryption=True
            )
            gcp_credentials_dict = json.loads(ssm_response['Parameter']['Value'])

            # Vertex AI 초기화
            credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
            project_id = gcp_credentials_dict['project_id']

            vertexai.init(project=project_id, credentials=credentials)
            gemini_pro_model = GenerativeModel(MODEL_ID_GEMINI)
            logger.info(f"Vertex AI (Gemini) 초기화 성공. Project: {project_id}")
        else:
            logger.warning("GCP_SSM_PARAM_NAME 환경변수가 설정되지 않아 Gemini 초기화를 건너뜁니다.")

    except Exception as e:
        logger.error(f"Vertex AI (Gemini) 초기화 실패: {e}")
        # 초기화 실패 시에도 Lambda 전체가 죽지 않도록 처리 (Bedrock은 사용 가능)
else:
    logger.info("Gemini 관련 라이브러리가 없어 Vertex AI 초기화를 건너뜁니다.")


# --- Public Functions ---

def get_embedding(text: str) -> list[float]:
    """텍스트를 Bedrock Titan 임베딩으로 변환합니다."""
    body = json.dumps({"inputText": text})
    try:
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=MODEL_ID_BEDROCK_EMBEDDING,
            contentType='application/json',
            accept='application/json'
        )
        response_body = json.loads(response.get('body').read())
        return response_body.get('embedding')
    except ClientError as e:
        logger.error(f"Bedrock 임베딩 생성 오류: {e}")
        raise e

def get_llm_response(prompt: str, use_bedrock: bool = False) -> str:
    """
    플래그 값에 따라 적절한 LLM 서비스(Bedrock Claude 또는 Gemini)를 호출합니다.
    """
    if use_bedrock:
        return _get_bedrock_response(prompt)
    else:
        return _get_gemini_direct_response(prompt)


# --- Private Functions ---

def _get_bedrock_response(prompt: str) -> str:
    """AWS Bedrock (Claude 3.5 Sonnet) 호출"""
    logger.info(f"Bedrock 호출 ({MODEL_ID_BEDROCK_CLAUDE})")

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId=MODEL_ID_BEDROCK_CLAUDE
        )
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except ClientError as e:
        logger.error(f"Bedrock API 오류: {e}")
        return _create_error_json_string(f"Bedrock 오류: {e}")
    except Exception as e:
        logger.error(f"Bedrock 알 수 없는 오류: {e}")
        return _create_error_json_string(f"시스템 오류: {e}")

def _get_gemini_direct_response(prompt: str) -> str:
    """Google Vertex AI (Gemini) 호출"""
    if not gemini_pro_model:
        logger.error("Gemini 모델이 초기화되지 않았습니다.")
        return _create_error_json_string("Gemini 서비스가 설정되지 않았습니다.")

    logger.info(f"Gemini 호출 ({MODEL_ID_GEMINI})")
    try:
        response = gemini_pro_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API 오류: {e}")
        return _create_error_json_string(f"Gemini 오류: {e}")

def _create_error_json_string(error_message: str) -> str:
    """에러 발생 시 사용자에게 보여줄 Fallback JSON 문자열 생성"""
    error_obj = {
        "answer": f"죄송합니다. 처리 중 문제가 발생했습니다.\n(상세: {error_message})",
        "services": []
    }
    return json.dumps(error_obj, ensure_ascii=False)
