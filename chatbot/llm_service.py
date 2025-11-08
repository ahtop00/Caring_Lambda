import json
import boto3
import anthropic
import logging
from botocore.exceptions import ClientError
from config import config

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from google.oauth2 import service_account # Lambda 인증에 필요
except ImportError:
    print("필수 라이브러리가 설치되지 않았습니다. 'pip install google-cloud-aiplatform google-auth'를 실행하세요.")
    vertexai = None
    GenerativeModel = None
    service_account = None

logger = logging.getLogger()

# --- 클라이언트 초기화 (한 번만 실행) ---
bedrock_runtime = boto3.client(service_name='bedrock-runtime')

anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key) if config.anthropic_api_key else None

gemini_pro_model = None
if vertexai and service_account:
    try:
        gcp_ssm_name = config.gcp_ssm_name
        if not gcp_ssm_name:
        # 환경 변수가 설정되지 않았으면 Gemini를 초기화하지 않습니다.
            raise ValueError("GCP_SSM_PARAM_NAME 환경 변수가 설정되지 않았습니다.")

        ssm_client = boto3.client('ssm')

        #    SSM에서 암호화된 파라미터(GCP 키 JSON 문자열)를 가져옵니다.
        ssm_response = ssm_client.get_parameter(
            Name=gcp_ssm_name,
            WithDecryption=True
        )
        secret_string = ssm_response['Parameter']['Value']

        # JSON 문자열을 Python 딕셔너리로 변환합니다.
        gcp_credentials_dict = json.loads(secret_string)
        # 딕셔너리로부터 GCP 인증 객체를 생성합니다.
        credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
        # Project ID는 키 파일에서 읽어와 vertexai.init()에 명시적으로 전달합니다.
        GEMINI_PROJECT_ID = gcp_credentials_dict['project_id']
        vertexai.init(project=GEMINI_PROJECT_ID, credentials=credentials)

        gemini_pro_model = GenerativeModel("gemini-2.5-pro")
        logger.info(f"Vertex AI (Gemini) 초기화 성공. 프로젝트: {GEMINI_PROJECT_ID} (via SSM)")

    except Exception as e:
        logger.error(f"Vertex AI (Gemini) 초기화 실패: {e}")
        logger.error("SSM 파라미터 이름이 올바른지, Lambda 역할에 'ssm:GetParameter' 권한이 있는지 확인하세요.")
else:
    logger.warning("Gemini를 사용하려면 'google-cloud-aiplatform'와 'google-auth' 라이브러리가 필요합니다.")


# --- 임베딩 함수 ---

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
        return _create_error_json_response(f"Bedrock API 오류: {e}")

def _get_anthropic_direct_response(prompt: str) -> str:
    """[내부 함수] Anthropic API를 직접 호출합니다."""
    ## 현재 메소드는 토큰 부족으로 사용하지 않습니다.
    if not anthropic_client:
        logger.error("Anthropic 클라이언트가 초기화되지 않았습니다. (API 키 확인)")
        return _create_error_json_response("Anthropic 클라이언트가 초기화되지 않았습니다.")

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
        return _create_error_json_response(f"Anthropic API 오류: {e}")

def _get_gemini_direct_response(prompt: str) -> str:
    """[내부 함수] Gemini API를 직접 호출합니다."""

    if not gemini_pro_model:
        logger.error("Gemini (Vertex AI) 모델이 로드되지 않았습니다.")
        return _create_error_json_response("Gemini (Vertex AI) 모델이 초기화되지 않았습니다.")

    logger.info("Gemini (Vertex AI) API를 직접 호출합니다.")
    try:
        response = gemini_pro_model.generate_content(prompt)

        return response.text

    except Exception as e:
        logger.error(f"Gemini API 호출 중 예외 발생: {e}")
        return _create_error_json_response(f"Gemini API 오류: {e}")

def _create_error_json_response(error_message: str) -> str:
    error_obj = {
        "answer": f"죄송합니다. LLM 응답 중 오류가 발생했습니다. (오류: {error_message})",
        "services": []
    }
    return json.dumps(error_obj, ensure_ascii=False)


# --- 메인 호출 함수 (public) ---

def get_llm_response(prompt: str, use_bedrock: bool = False) -> str:
    """
    use_bedrock 플래그 값에 따라 적절한 LLM 서비스를 선택하여 호출합니다.

    :param prompt: LLM에 전달할 프롬프트 문자열
    :param use_bedrock: True이면 Bedrock, False이면 Gemini 직접 API를 사용
    :return: LLM의 응답 문자열
    """
    if use_bedrock:
        return _get_bedrock_response(prompt)
    else:
        # (use_bedrock=False)일 때 Gemini 호출
        return _get_gemini_direct_response(prompt)
