# chatbot/config.py
import os
import logging

logger = logging.getLogger()

class AppConfig:
    def __init__(self):
        # DB 설정
        self.db_host = os.environ['DB_HOST']
        self.db_name = os.environ['DB_NAME']
        self.db_user = os.environ['DB_USER']
        self.db_password = os.environ['DB_PASSWORD']

        # AI 서비스 설정
        self.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.gcp_ssm_param_name = os.environ.get('GCP_SSM_PARAM_NAME')

        # SQS 설정
        self.cbt_log_sqs_url = os.environ.get('CBT_LOG_SQS_URL')

        # 필수값 검증
        if not all([self.db_host, self.db_name, self.db_user, self.db_password]):
            msg = "데이터베이스 환경 변수가 하나 이상 누락되었습니다."
            logger.error(msg)
            raise ValueError(msg)

        # (선택 사항) SQS URL이 없으면 경고 로그
        if not self.cbt_log_sqs_url:
            logger.warning("CBT_LOG_SQS_URL 환경 변수가 설정되지 않았습니다. 로그 저장이 비활성화됩니다.")

config = AppConfig()
