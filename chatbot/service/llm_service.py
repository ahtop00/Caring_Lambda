import json
import boto3
import logging
from botocore.exceptions import ClientError
from functools import lru_cache
from openai import OpenAI, OpenAIError
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

    # vLLM에 로드된 모델명 (서버 로그나 curl /v1/models로 확인된 ID 사용)
    # 만약 이름을 모르면 "/workspace/" 혹은 "default" 등을 시도
    MODEL_ID_GEMMA = "0xMori/gemma-2-9b-safori-cbt-merged"

    def __init__(self):
        # AWS Client 초기화
        self.bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='ap-northeast-2')

        # Vertex AI (Gemini) 초기화
        self.gemini_pro_model = self._init_gemini()

        # Hugging Face (vLLM) 클라이언트 초기화
        self.hf_client = self._init_hf_client()

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

    def _init_hf_client(self):
        """
        OpenAI 호환 클라이언트를 초기화합니다 (vLLM용)
        """
        if not config.hf_endpoint_url or not config.hf_api_token:
            logger.warning("HF Endpoint URL 또는 Token이 설정되지 않아 vLLM 클라이언트를 초기화하지 않습니다.")
            return None

        try:
            # vLLM/OpenAI 호환 주소 처리: 끝에 /v1 붙이기
            base_url = f"{config.hf_endpoint_url.rstrip('/')}/v1"

            client = OpenAI(
                base_url=base_url,
                api_key=config.hf_api_token
            )
            logger.info("HF vLLM(OpenAI) 클라이언트 초기화 성공")
            return client
        except Exception as e:
            logger.error(f"HF 클라이언트 초기화 실패: {e}")
            return None

    def get_gemma_response(self, prompt: str, max_tokens: int = 2048) -> str:
        """
        vLLM에 배포된 Gemma 3 모델을 호출합니다. (OpenAI SDK 사용)
        """

        if not self.hf_client:
            error_msg = "오류: vLLM 클라이언트가 초기화되지 않았습니다. 설정을 확인하세요."
            logger.error(error_msg)
            return json.dumps({"empathy": error_msg}, ensure_ascii=False)

        messages = [
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.hf_client.chat.completions.create(
                model=self.MODEL_ID_GEMMA,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9
            )

            result_text = response.choices[0].message.content
            return result_text

        except OpenAIError as e:
            logger.error(f"vLLM 호출 오류 (OpenAI Error): {e}")
            return json.dumps({"empathy": f"AI 모델 오류: {str(e)}"}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Gemma 연결 알 수 없는 오류: {e}")
            return json.dumps({"empathy": f"시스템 오류: {str(e)}"}, ensure_ascii=False)

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
