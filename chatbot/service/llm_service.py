# chatbot/service/llm_service.py
import json
import boto3
import logging
from botocore.exceptions import ClientError
from functools import lru_cache

try:
    from config import config
except ImportError:
    from ..config import config

# Optional: Vertex AI
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from google.oauth2 import service_account
except ImportError:
    vertexai = None

logger = logging.getLogger()

class LLMService:
    MODEL_ID_BEDROCK_CLAUDE = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    MODEL_ID_BEDROCK_EMBEDDING = 'amazon.titan-embed-text-v2:0'
    MODEL_ID_GEMINI = "gemini-2.5-pro"

    def __init__(self):
        # AWS Client 초기화
        self.bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='ap-northeast-2')

        # Vertex AI (Gemini) 초기화
        self.gemini_pro_model = self._init_gemini()

    def _init_gemini(self):
        if not vertexai:
            logger.info("Gemini 라이브러리 없음")
            return None

        try:
            gcp_ssm_name = config.gcp_ssm_param_name
            if gcp_ssm_name:
                ssm_client = boto3.client('ssm', region_name='ap-northeast-2')
                ssm_response = ssm_client.get_parameter(Name=gcp_ssm_name, WithDecryption=True)
                gcp_credentials_dict = json.loads(ssm_response['Parameter']['Value'])

                credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
                project_id = gcp_credentials_dict['project_id']

                vertexai.init(project=project_id, credentials=credentials)
                logger.info(f"Vertex AI 초기화 성공: {project_id}")
                return GenerativeModel(self.MODEL_ID_GEMINI)
        except Exception as e:
            logger.error(f"Vertex AI 초기화 실패: {e}")
            return None

    def get_embedding(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text})
        try:
            response = self.bedrock_runtime.invoke_model(
                body=body,
                modelId=self.MODEL_ID_BEDROCK_EMBEDDING,
                contentType='application/json',
                accept='application/json'
            )
            response_body = json.loads(response.get('body').read())
            return response_body.get('embedding')
        except ClientError as e:
            logger.error(f"Bedrock 임베딩 오류: {e}")
            raise e

    def get_llm_response(self, prompt: str, use_bedrock: bool = False) -> str:
        if use_bedrock:
            return self._get_bedrock_response(prompt)
        else:
            return self._get_gemini_direct_response(prompt)

    def _get_bedrock_response(self, prompt: str) -> str:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            response = self.bedrock_runtime.invoke_model(
                body=json.dumps(request_body),
                modelId=self.MODEL_ID_BEDROCK_CLAUDE
            )
            response_body = json.loads(response.get('body').read())
            return response_body['content'][0]['text']
        except Exception as e:
            logger.error(f"Bedrock 오류: {e}")
            return self._create_error_json(f"시스템 오류: {e}")

    def _get_gemini_direct_response(self, prompt: str) -> str:
        if not self.gemini_pro_model:
            return self._create_error_json("Gemini 미설정")
        try:
            response = self.gemini_pro_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini 오류: {e}")
            return self._create_error_json(f"Gemini 오류: {e}")

    def _create_error_json(self, msg: str) -> str:
        return json.dumps({"answer": f"오류 발생: {msg}", "services": []}, ensure_ascii=False)

# --- 의존성 주입용 (Singleton 패턴) ---
@lru_cache()
def get_llm_service() -> LLMService:
    return LLMService()
