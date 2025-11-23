# chatbot/test/conftest.py
import os
import sys
import pytest
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 환경 변수 설정 로직
if os.environ.get("TEST_SCOPE") == "integration":
    # 1. 통합 테스트 모드: 실제 .env 파일 로드
    print("⚠️ [Integration Test] Loading real .env file...")
    load_dotenv() # .env 파일의 내용을 os.environ에 적재
else:
    # 2. 단위 테스트 모드 (기본): 가짜 환경 변수 설정
    os.environ["DB_HOST"] = "test_host"
    os.environ["DB_NAME"] = "test_db"
    os.environ["DB_USER"] = "test_user"
    os.environ["DB_PASSWORD"] = "test_password"
    os.environ["CBT_LOG_SQS_URL"] = "https://sqs.dummy.url"
    os.environ["GCP_SSM_PARAM_NAME"] = "dummy_param"
    os.environ["ANTHROPIC_API_KEY"] = "dummy_key"

# 통합 테스트용 마커 등록
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")
