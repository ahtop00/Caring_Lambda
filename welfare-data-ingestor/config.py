# -*- coding: utf-8 -*-
import os
import logging

logger = logging.getLogger()

def get_env_variable(var_name, default=None):
    """환경 변수를 로드하거나, 없을 경우 에러를 발생시킵니다."""
    value = os.environ.get(var_name, default)
    if value is None:
        error_msg = f"FATAL: 필수 환경 변수가 누락되었습니다: {var_name}"
        logger.error(error_msg)
        raise KeyError(error_msg)
    return value

def get_int_env_variable(var_name, default):
    """정수형 환경 변수를 로드합니다."""
    try:
        return int(os.environ.get(var_name, default))
    except ValueError:
        logger.error(f"환경 변수 {var_name}이 정수가 아닙니다. 기본값 {default}을 사용합니다.")
        return default

# ===== API Fetcher용 변수 =====
API_ENDPOINT = get_env_variable("API_ENDPOINT")
SERVICE_KEY  = get_env_variable("SERVICE_KEY")
ROWS_PER_PAGE = get_int_env_variable("ROWS_PER_PAGE", 100)
PAGE_LIMIT    = get_int_env_variable("PAGE_LIMIT", 100)
START_PAGE    = get_int_env_variable("START_PAGE", 1)

# ===== Vector DB Ingestor용 변수 =====
DB_CONFIG = {
    'host': get_env_variable('DB_HOST'),
    'dbname': get_env_variable('DB_NAME'),
    'user': get_env_variable('DB_USER'),
    'password': get_env_variable('DB_PASSWORD')
}

# ===== Bedrock용 변수 =====
BEDROCK_MODEL_ID = get_env_variable("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")

# ===== API 상수 =====
# API 파라미터 중 고정값
API_CONSTANT_PARAMS = {
    "trgterIndvdlArray": "040", # 장애인
    "srchKeyCode": "003",       # 상세내용
    "arrgOrd": "001"            # 최종수정일
}
