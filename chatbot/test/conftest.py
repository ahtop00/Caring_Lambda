# chatbot/test/conftest.py
import os
import sys

os.environ["DB_HOST"] = "test_host"
os.environ["DB_NAME"] = "test_db"
os.environ["DB_USER"] = "test_user"
os.environ["DB_PASSWORD"] = "test_password"
os.environ["CBT_LOG_SQS_URL"] = "https://sqs.dummy.url"
os.environ["GCP_SSM_PARAM_NAME"] = "dummy_param"
os.environ["ANTHROPIC_API_KEY"] = "dummy_key"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
