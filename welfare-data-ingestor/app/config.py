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
        logger.warning(f"환경 변수 {var_name}이 정수가 아닙니다. 기본값 {default}을 사용합니다.")
        return default

# ===== 1. 지자체 API 변수 =====
LOCAL_API_ENDPOINT = get_env_variable("LOCAL_API_ENDPOINT")
LOCAL_API_KEY      = get_env_variable("LOCAL_API_KEY")
LOCAL_ROWS_PER_PAGE = get_int_env_variable("LOCAL_ROWS_PER_PAGE", 100)
LOCAL_PAGE_LIMIT    = get_int_env_variable("LOCAL_PAGE_LIMIT", 5)
LOCAL_START_PAGE    = get_int_env_variable("LOCAL_START_PAGE", 1)

# ===== 중앙부처 API 변수 =====
CENTRAL_API_ENDPOINT = get_env_variable("CENTRAL_API_ENDPOINT")
CENTRAL_API_KEY      = get_env_variable("CENTRAL_API_KEY")
CENTRAL_ROWS_PER_PAGE = get_int_env_variable("CENTRAL_ROWS_PER_PAGE", 100)
CENTRAL_PAGE_LIMIT    = get_int_env_variable("CENTRAL_PAGE_LIMIT", 5)
CENTRAL_START_PAGE    = get_int_env_variable("CENTRAL_START_PAGE", 1)

# ===== 장애인 구인정보 API 변수 =====
EMPLOYMENT_API_ENDPOINT = get_env_variable("EMPLOYMENT_API_ENDPOINT")
EMPLOYMENT_API_KEY = get_env_variable("EMPLOYMENT_API_KEY")
EMPLOYMENT_ROWS_PER_PAGE = get_int_env_variable("EMPLOYMENT_ROWS_PER_PAGE", 30)
EMPLOYMENT_PAGE_LIMIT = get_int_env_variable("EMPLOYMENT_PAGE_LIMIT", 5)
EMPLOYMENT_START_PAGE = get_int_env_variable("EMPLOYMENT_START_PAGE", 1)


# ===== Vector DB Ingestor용 변수 =====
DB_CONFIG = {
    'host': get_env_variable('DB_HOST'),
    'dbname': get_env_variable('DB_NAME'),
    'user': get_env_variable('DB_USER'),
    'password': get_env_variable('DB_PASSWORD')
}

# ===== Bedrock용 변수 =====
BEDROCK_MODEL_ID = get_env_variable("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")

# ===== SQS Queue URL 변수=====
# 복지 정책 Ingestor에서 사용할 SQS
WELFARE_SQS_QUEUE_URL = get_env_variable(
    "WELFARE_SQS_QUEUE_URL",
    default="https://sqs.ap-northeast-2.amazonaws.com/084056488795/policy-sqs"
)

#  구인 정보 Ingestor가 사용하게 될 SQS
EMPLOYMENT_SQS_QUEUE_URL = get_env_variable(
    "EMPLOYMENT_SQS_QUEUE_URL",
    default="https://sqs.ap-northeast-2.amazonaws.com/084056488795/jobOpening-sqs"
)

# ===== 지자체 API 상수 =====
API_CONSTANT_PARAMS = {
    "trgterIndvdlArray": "040", # 장애인
    "srchKeyCode": "003",       # 상세내용
    "arrgOrd": "001"            # 최종수정일
}

# ==== 중앙부처 API 고정 파라미터 ====
CENTRAL_API_CONSTANT_PARAMS = {
    "srchKeyCode": "003", # 제목+내용
    "orderBy": "date",
    "trgterIndvdlArray": "040"
}
