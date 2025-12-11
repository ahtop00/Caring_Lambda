# chatbot/test/services/test_reframing_service.py
import pytest
import json
from unittest.mock import Mock
from schema.reframing import ReframingRequest, VoiceReframingRequest
from domain.reframing_logic import ReframingService
from repository.chat_repository import ChatRepository
from service.llm_service import LLMService

def test_execute_reframing_success():
    """
    [Scenario] 텍스트 상담: LLM 응답 처리 및 동기 DB 저장(임베딩 포함) 테스트
    """
    # 1. Mock 객체들 준비
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    # [NEW] 임베딩 생성 Mock 설정 (동기 저장 과정에서 호출됨)
    mock_llm_service.get_embedding.return_value = [0.1] * 1024

    # 2. 시나리오 데이터 설정
    mock_chat_repo.get_chat_history.return_value = []

    # (2-2) LLM이 리턴할 가짜 JSON (top_emotion 포함)
    llm_output = {
        "empathy": "많이 힘드셨군요.",
        "detected_distortion": "흑백논리",
        "analysis": "분석 내용...",
        "socratic_question": "질문?",
        "alternative_thought": "대안",
        "top_emotion": "anxiety"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    # 3. Service 생성 (SQS 관련 의존성 제거됨)
    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # 4. 실행
    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="난 망했어")
    result = service.execute_reframing(request)

    # 5. 검증
    # (5-1) 응답 필드 변환 확인 (top_emotion -> emotion)
    expected_result = llm_output.copy()
    expected_result["emotion"] = expected_result.pop("top_emotion")
    assert result == expected_result

    # (5-2) 주요 메서드 호출 확인
    mock_chat_repo.get_chat_history.assert_called_once()
    mock_llm_service.get_llm_response.assert_called_once()

    # [NEW] 동기 저장 로직 검증
    # 임베딩 생성이 호출되었는가?
    mock_llm_service.get_embedding.assert_called_once_with("난 망했어")
    # DB 저장이 수행되었는가? (유령 읽기 방지 핵심)
    mock_chat_repo.log_cbt_session.assert_called_once()

    # 저장된 데이터 검증
    _, kwargs = mock_chat_repo.log_cbt_session.call_args
    assert kwargs["user_id"] == "user1"
    assert kwargs["session_id"] == "sess1"
    assert kwargs["embedding"] == [0.1] * 1024  # 임베딩이 잘 전달되었는지


def test_execute_reframing_llm_failure():
    """
    [Scenario] LLM 응답 실패(Fallback) 시에도 DB 저장이 수행되는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    # 임베딩 Mock
    mock_llm_service.get_embedding.return_value = [0.0] * 1024

    mock_chat_repo.get_chat_history.return_value = []
    mock_llm_service.get_llm_response.return_value = "JSON 아님 Error"

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="테스트")
    result = service.execute_reframing(request)

    # 검증: Fallback 응답 확인
    assert result["detected_distortion"] == "분석 불가"
    assert result.get("emotion") == "neutral"

    # [NEW] 실패 상황에서도 로그 저장은 시도해야 함
    mock_chat_repo.log_cbt_session.assert_called_once()


def test_execute_voice_reframing_success():
    """
    [Scenario] 음성 상담: 동기 저장 시 S3 URL 등이 잘 전달되는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    # 임베딩 Mock
    mock_llm_service.get_embedding.return_value = [0.1] * 1024

    mock_chat_repo.get_chat_history.return_value = []

    llm_output = {
        "empathy": "목소리에서 슬픔이 느껴지네요.",
        "detected_distortion": "없음",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    voice_request = VoiceReframingRequest(
        user_id="user_voice",
        session_id="sess_voice",
        user_input="너무 슬퍼요",
        emotion={"top_emotion": "sad", "confidence": 0.95},
        s3_url="https://s3.bucket/file.mp3"  # S3 URL 포함
    )

    result = service.execute_voice_reframing(voice_request)

    assert result["empathy"] == "목소리에서 슬픔이 느껴지네요."
    assert result["emotion"] == "sad"

    # 동기 저장 및 파라미터 확인
    mock_chat_repo.log_cbt_session.assert_called_once()

    _, kwargs = mock_chat_repo.log_cbt_session.call_args
    assert kwargs["user_id"] == "user_voice"
    assert kwargs["s3_url"] == "https://s3.bucket/file.mp3" # URL이 DB 저장 메서드까지 잘 갔는지 확인
