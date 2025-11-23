import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from datetime import datetime

from main import app
from domain.chat_logic import get_chat_service
from schema.history import ChatHistoryResponse, ChatMessage
from exception import AppError

# TestClient 생성
client = TestClient(app)

def test_get_history_success():
    """
    [Scenario] 채팅 내역 조회 API (GET /chatbot/history/{session_id}) 성공 테스트
    """
    # 1. 가짜 Service 생성
    mock_chat_service = Mock()

    # Service가 반환할 데이터 설정
    expected_response = ChatHistoryResponse(
        session_id="test_session",
        messages=[
            ChatMessage(role="user", content="안녕", timestamp=datetime.now()),
            ChatMessage(role="assistant", content="안녕하세요", timestamp=datetime.now())
        ],
        total_page=1,
        current_page=1
    )
    mock_chat_service.get_session_history.return_value = expected_response

    # 2. 의존성 오버라이드 (핵심!)
    # "get_chat_service를 호출하면 내가 만든 mock_chat_service를 줘라"
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service

    # 3. 요청 보내기
    response = client.get("/chatbot/history/test_session?page=1")

    # 4. 검증
    assert response.status_code == 200
    json_res = response.json()
    assert json_res["session_id"] == "test_session"
    assert len(json_res["messages"]) == 2

    # 의존성 초기화 (다른 테스트에 영향 안 주게)
    app.dependency_overrides = {}

def test_get_history_validation_error():
    """
    [Scenario] page 파라미터에 숫자가 아닌 문자를 넣었을 때 422 에러가 나는지 테스트
    """
    # [수정] 이 테스트에서도 DB 연결을 막기 위해 가짜 의존성을 주입해야 합니다.
    app.dependency_overrides[get_chat_service] = lambda: Mock()

    # 요청 실행
    response = client.get("/chatbot/history/test_session?page=invalid_number")

    # [수정] 테스트 종료 후 초기화
    app.dependency_overrides = {}

    # 422 Unprocessable Entity
    assert response.status_code == 422

    # 우리가 만든 전역 핸들러가 작동했는지 확인 (error, code 필드 확인)
    json_res = response.json()
    assert json_res["error"] is True
    assert json_res["code"] == 422
    # detail 메시지에 "page" 관련 내용이 있는지
    assert "page" in json_res["detail"] or "type_error" in json_res["detail"] or "Input should be a valid integer" in json_res["detail"]

def test_get_history_service_error():
    """
    [Scenario] Service에서 AppError(500)를 던졌을 때, 컨트롤러가 500 응답을 잘 주는지 테스트
    """
    mock_chat_service = Mock()
    # Service가 에러를 던지도록 설정
    mock_chat_service.get_session_history.side_effect = AppError(
        status_code=500,
        message="DB 연결 실패",
        detail="Connection refused"
    )

    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service

    response = client.get("/chatbot/history/test_session")

    assert response.status_code == 500
    json_res = response.json()
    assert json_res["code"] == 500
    assert json_res["message"] == "DB 연결 실패" # 우리가 설정한 메시지

    app.dependency_overrides = {}
