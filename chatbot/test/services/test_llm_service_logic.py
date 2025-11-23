# chatbot/test/services/test_llm_service_logic.py
import pytest
import json
from unittest.mock import patch, Mock
from service.llm_service import LLMService

@patch("boto3.client") # boto3를 가로챔
def test_get_embedding_success(mock_boto_client):
    """
    [Scenario] Bedrock을 호출하여 임베딩을 가져오는 로직 테스트
    """
    # 1. Mock 설정
    mock_bedrock = mock_boto_client.return_value
    # Bedrock 응답 구조 흉내
    mock_response_body = json.dumps({"embedding": [0.1, 0.2, 0.3]})
    mock_bedrock.invoke_model.return_value = {
        "body": Mock(read=lambda: mock_response_body)
    }

    # 2. 서비스 생성 (여기서 boto3.client가 호출됨 -> mock_bedrock 반환)
    service = LLMService()

    # 3. 실행
    vector = service.get_embedding("테스트")

    # 4. 검증
    assert vector == [0.1, 0.2, 0.3]
    mock_bedrock.invoke_model.assert_called_once()

@patch("boto3.client")
def test_get_bedrock_response_success(mock_boto_client):
    """
    [Scenario] Bedrock Claude 호출 테스트
    """
    mock_bedrock = mock_boto_client.return_value
    mock_response_body = json.dumps({
        "content": [{"text": "안녕하세요"}]
    })
    mock_bedrock.invoke_model.return_value = {
        "body": Mock(read=lambda: mock_response_body)
    }

    service = LLMService()
    response = service.get_llm_response("안녕", use_bedrock=True)

    assert response == "안녕하세요"
