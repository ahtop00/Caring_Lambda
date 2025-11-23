import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from service.worker_service import process_sqs_batch

# worker_service 내부에서 import하는 것들을 가로채기(patch) 위해 데코레이터 사용
@patch("service.worker_service.ChatRepository")      # 1. Repo 클래스 자체를 가짜로 대체
@patch("service.worker_service.get_llm_service")     # 2. LLM 서비스 팩토리 함수 가짜로 대체
@patch("service.worker_service.get_db_conn")         # 3. DB 연결 제너레이터 함수 가짜로 대체
def test_process_sqs_batch_success(mock_get_db_conn, mock_get_llm, MockChatRepo):
    """
    [Scenario] 정상적인 SQS 메시지 2개가 들어왔을 때 처리 성공 테스트
    """
    # --- [A] Mock 설정 ---

    # 1. DB Connection Generator Mocking
    # worker_service가 db_gen = get_db_conn() -> next(db_gen) 호출함
    mock_db_gen = MagicMock()
    mock_conn = Mock()
    # 첫 번째 next() 호출엔 conn 반환, 두 번째(finally)엔 StopIteration 발생
    mock_db_gen.__next__.side_effect = [mock_conn, StopIteration]
    mock_get_db_conn.return_value = mock_db_gen

    # 2. LLM Service Mocking
    mock_llm_instance = Mock()
    mock_llm_instance.get_embedding.return_value = [0.1, 0.2, 0.3] # 가짜 임베딩 벡터
    mock_get_llm.return_value = mock_llm_instance

    # 3. Repository Instance Mocking
    # ChatRepository(conn) 호출 시 반환될 가짜 인스턴스
    mock_repo_instance = MockChatRepo.return_value

    # --- [B] 테스트 데이터 준비 ---
    records = [
        {
            "body": json.dumps({
                "user_id": "user_1",
                "session_id": "session_A",
                "user_input": "안녕하세요",
                "bot_response": {"empathy": "반가워요"}
            })
        },
        {
            "body": json.dumps({
                "user_id": "user_2",
                "session_id": "session_B",
                "user_input": "테스트입니다",
                "bot_response": {}
            })
        }
    ]

    # --- [C] 실행 ---
    result = process_sqs_batch(records)

    # --- [D] 검증 ---
    assert result["status"] == "completed"
    assert result["success"] == 2
    assert result["failed"] == 0

    # DB 연결이 생성되고 닫혔는지 확인
    mock_get_db_conn.assert_called_once()
    assert mock_db_gen.__next__.call_count >= 1 # 최소한 연결을 열기 위해 호출됨

    # LLM 임베딩 생성이 2번 호출되었는지 확인
    assert mock_llm_instance.get_embedding.call_count == 2

    # DB 저장 함수가 2번 호출되었는지 확인
    assert mock_repo_instance.log_cbt_session.call_count == 2

    # 첫 번째 호출 인자 확인
    _, kwargs = mock_repo_instance.log_cbt_session.call_args_list[0]
    assert kwargs["session_id"] == "session_A"


@patch("service.worker_service.ChatRepository")
@patch("service.worker_service.get_llm_service")
@patch("service.worker_service.get_db_conn")
def test_process_sqs_batch_partial_fail(mock_get_db_conn, mock_get_llm, MockChatRepo):
    """
    [Scenario] JSON 파싱 에러나 필수 필드 누락이 있을 때 집계 테스트
    """
    # Mock 설정 (위와 동일하게 기본 설정)
    mock_db_gen = MagicMock()
    mock_db_gen.__next__.return_value = Mock()
    mock_get_db_conn.return_value = mock_db_gen

    mock_repo_instance = MockChatRepo.return_value

    # 테스트 데이터: 1개 성공, 1개 JSON 에러, 1개 필드 누락
    records = [
        { "body": json.dumps({"user_id": "u1", "session_id": "s1", "user_input": "ok", "bot_response": {}}) }, # 성공
        { "body": "이건 JSON이 아닙니다" }, # 실패 (JSONDecodeError)
        { "body": json.dumps({"user_id": "u2"}) } # 실패 (필수 필드 누락)
    ]

    # 실행
    result = process_sqs_batch(records)

    # 검증
    assert result["processed"] == 3
    assert result["success"] == 1
    assert result["failed"] == 2

    # 성공한 1건에 대해서만 저장이 시도되었는지 확인
    mock_repo_instance.log_cbt_session.assert_called_once()
