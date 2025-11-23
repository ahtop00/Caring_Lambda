import pytest
import json
from unittest.mock import Mock, patch
from schema.reframing import ReframingRequest
from domain.reframing_logic import ReframingService
from repository.chat_repository import ChatRepository
from service.llm_service import LLMService

# SQS Client(boto3)는 __init__에서 생성되므로 patch로 가로채야 함
@patch('boto3.client')
def test_execute_reframing_success(mock_boto_client):
    """
    [Scenario] LLM이 정상적인 JSON을 줬을 때, 결과 반환 및 SQS 전송 테스트
    """
    # 1. Mock 객체들 준비
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)
    mock_sqs = mock_boto_client.return_value

    # 2. 시나리오 데이터 설정
    # (2-1) 이전 대화 기록 없음
    mock_chat_repo.get_chat_history.return_value = []

    # (2-2) LLM이 리턴할 "가짜" JSON 문자열
    expected_response = {
        "empathy": "많이 힘드셨군요.",
        "detected_distortion": "흑백논리",
        "analysis": "분석 내용...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(expected_response)

    # 3. Service 생성 (Mock 주입)
    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # 4. 실행
    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="난 망했어")
    result = service.execute_reframing(request)

    # 5. 검증
    # 결과값이 LLM이 준 데이터와 같은지
    assert result == expected_response

    # Repository가 호출되었는지
    mock_chat_repo.get_chat_history.assert_called_once()

    # LLM 서비스가 호출되었는지
    mock_llm_service.get_llm_response.assert_called_once()

    # SQS 전송이 시도되었는지 (SQS URL이 config에 있다고 가정 시)
    # (config 값을 테스트 중에 조작하려면 mock.patch.object(config, 'cbt_log_sqs_url', 'fake_url') 필요)
    # 여기서는 서비스가 정상적으로 mock_sqs를 가지고 있는지 정도만 확인
    assert service.sqs_client == mock_sqs

@patch('boto3.client')
def test_execute_reframing_llm_failure(mock_boto_client):
    """
    [Scenario] LLM이 이상한 문자열(JSON 아님)을 줬을 때, Fallback 응답이 나가는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_chat_repo.get_chat_history.return_value = []

    # LLM이 JSON이 아닌 일반 텍스트를 반환함 (에러 상황)
    mock_llm_service.get_llm_response.return_value = "JSON 형식이 아님. 그냥 말함."

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="테스트")
    result = service.execute_reframing(request)

    # 검증: Fallback 응답이 왔는지 확인
    assert result["detected_distortion"] == "분석 불가"
    assert "오류" in result["analysis"] or "발생" in result["analysis"]
