import pytest
import json
from unittest.mock import Mock, patch
from schema.reframing import ReframingRequest, VoiceReframingRequest
from domain.reframing_logic import ReframingService
from repository.chat_repository import ChatRepository
from service.llm_service import LLMService

# SQS Client(boto3)는 __init__에서 생성되므로 patch로 가로채야 함
@patch('boto3.client')
def test_execute_reframing_success(mock_boto_client):
    """
    [Scenario] 텍스트 상담: LLM이 top_emotion을 포함한 정상 JSON을 줬을 때
    -> emotion 필드로 변환되어 반환되는지 테스트
    """
    # 1. Mock 객체들 준비
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)
    mock_sqs = mock_boto_client.return_value

    # 2. 시나리오 데이터 설정
    mock_chat_repo.get_chat_history.return_value = []

    # (2-2) LLM이 리턴할 가짜 JSON (top_emotion 포함)
    llm_output = {
        "empathy": "많이 힘드셨군요.",
        "detected_distortion": "흑백논리",
        "analysis": "분석 내용...",
        "socratic_question": "질문?",
        "alternative_thought": "대안",
        "top_emotion": "anxiety"  # LLM은 top_emotion을 반환
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    # 3. Service 생성
    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # 4. 실행
    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="난 망했어")
    result = service.execute_reframing(request)

    # 5. 검증
    # 서비스 로직: top_emotion(LLM) -> emotion(Response) 필드명 변경 확인
    expected_result = llm_output.copy()
    expected_result["emotion"] = expected_result.pop("top_emotion")

    assert result == expected_result
    mock_chat_repo.get_chat_history.assert_called_once()
    mock_llm_service.get_llm_response.assert_called_once()

@patch('boto3.client')
def test_execute_reframing_llm_failure(mock_boto_client):
    """
    [Scenario] LLM 응답 실패 시 Fallback 응답에 emotion='neutral'이 있는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_chat_repo.get_chat_history.return_value = []
    mock_llm_service.get_llm_response.return_value = "JSON 아님 Error"

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="테스트")
    result = service.execute_reframing(request)

    # 검증: Fallback 응답 확인
    assert result["detected_distortion"] == "분석 불가"
    # Fallback에는 emotion이 "neutral"로 설정되어 있어야 함
    assert result.get("emotion") == "neutral"

@patch('boto3.client')
def test_execute_voice_reframing_success(mock_boto_client):
    """
    [Scenario] 음성 상담: 요청(Request)에 담긴 감정 데이터가 응답(Response)에 잘 반영되는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    # (1) 대화 내역 없음
    mock_chat_repo.get_chat_history.return_value = []

    # (2) LLM 응답 (여기엔 top_emotion이 없거나 있어도 무시되어야 함)
    llm_output = {
        "empathy": "목소리에서 슬픔이 느껴지네요.",
        "detected_distortion": "없음",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # (3) 요청 생성 (emotion 데이터 포함)
    # caring-back에서 분석된 감정이 "sad"라고 가정
    voice_request = VoiceReframingRequest(
        user_id="user_voice",
        session_id="sess_voice",
        user_input="너무 슬퍼요",
        emotion={"top_emotion": "sad", "confidence": 0.95}
    )

    # (4) 실행
    result = service.execute_voice_reframing(voice_request)

    # (5) 검증
    # LLM 응답 내용이 잘 들어갔는지
    assert result["empathy"] == "목소리에서 슬픔이 느껴지네요."

    # [핵심] 요청에 있던 'sad'가 응답의 'emotion' 필드로 잘 들어갔는지 확인
    assert result["emotion"] == "sad"

    # 프롬프트 생성 시 감정 정보가 포함되었는지 간접 확인 (LLM 호출 인자 검사)
    call_args = mock_llm_service.get_llm_response.call_args[0]
    prompt_used = call_args[0]
    assert "sad" in prompt_used # 프롬프트 텍스트 안에 'sad'가 포함되어 있어야 함
