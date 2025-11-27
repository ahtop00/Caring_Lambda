import pytest
from unittest.mock import Mock
from datetime import datetime

from domain.chat_logic import ChatService
from repository.chat_repository import ChatRepository
from schema.history import SessionListResponse, ChatHistoryResponse

def test_get_user_sessions_success():
    """
    [Scenario] DB에서 세션 목록을 가져왔을 때, Response 모델로 잘 변환되는지 테스트
    """
    # 1. 가짜(Mock) Repository 생성
    mock_repo = Mock(spec=ChatRepository)

    # 2. 가짜 데이터 준비 (DB에서 fetchall() 했을 때 나오는 튜플 형태)
    # (session_id, user_input, created_at, bot_response_json)
    mock_data = [
        ("session_1", "안녕하세요", datetime(2025, 1, 1, 12, 0, 0), {"detected_distortion": "흑백논리"}),
        ("session_2", "힘들어요", datetime(2025, 1, 2, 12, 0, 0), {}) # 왜곡 없음
    ]

    # 3. Mock 동작 설정: get_user_sessions가 호출되면 mock_data를 리턴
    mock_repo.get_user_sessions.return_value = mock_data

    # 4. Service에 Mock 주입
    service = ChatService(chat_repo=mock_repo)

    # 5. 실행
    result = service.get_user_sessions("test_user")

    # 6. 검증 (Assert)
    assert isinstance(result, SessionListResponse)
    assert len(result.sessions) == 2

    # 첫 번째 세션 검증
    assert result.sessions[0].session_id == "session_1"
    assert result.sessions[0].distortion_tags == ["흑백논리"]

    # 두 번째 세션 검증 (태그가 없어야 함)
    assert result.sessions[0].last_message == "안녕하세요"
    assert result.sessions[1].distortion_tags == []

    # Repository가 올바른 인자로 호출되었는지 확인
    mock_repo.get_user_sessions.assert_called_once_with("test_user")

def test_get_session_history_success():
    """
    [Scenario] 상세 대화 내용을 가져와서 User/Assistant 메시지로 잘 분리하는지 테스트
    """
    mock_repo = Mock(spec=ChatRepository)

    mock_rows = [
        ("나는 바보야", {"empathy": "그렇지 않아요.", "socratic_question": "왜죠?"}, datetime.now(), None)
    ]
    mock_total_count = 10

    # Mock 설정 (튜플 리턴)
    mock_repo.get_session_messages.return_value = (mock_rows, mock_total_count)

    service = ChatService(chat_repo=mock_repo)

    # 실행 (1페이지 요청)
    result = service.get_session_history("session_1", page=1)

    # 검증
    assert isinstance(result, ChatHistoryResponse)
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"
    assert result.messages[0].content == "나는 바보야"
    assert result.messages[0].s3_url is None

    assert result.messages[1].role == "assistant"
    assert result.messages[1].content == "그렇지 않아요. 왜죠?"
