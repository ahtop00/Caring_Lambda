# config.py
import os
import logging

logger = logging.getLogger()

class AppConfig:
    def __init__(self):
        self.db_host = os.environ['DB_HOST']
        self.db_name = os.environ['DB_NAME']
        self.db_user = os.environ['DB_USER']
        self.db_password = os.environ['DB_PASSWORD']
        self.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.gcp_ssm_param_name = os.environ.get('GCP_SSM_PARAM_NAME')

        if not all([self.db_host, self.db_name, self.db_user, self.db_password]):
            msg = "데이터베이스 환경 변수가 하나 이상 누락되었습니다."
            logger.error(msg)
            raise ValueError(msg)

config = AppConfig()
