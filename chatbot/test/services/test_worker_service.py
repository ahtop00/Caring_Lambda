import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from service.worker_service import process_sqs_batch

# 공통 Mock 설정 헬퍼
def setup_mocks(mock_get_db_conn, mock_get_llm, MockChatRepo):
    # 1. DB Connection Generator Mocking
    mock_db_gen = MagicMock()
    mock_conn = Mock()
    mock_db_gen.__next__.side_effect = [mock_conn, StopIteration]
    mock_get_db_conn.return_value = mock_db_gen

    # 2. LLM Service Mocking
    mock_llm_instance = Mock()
    mock_get_llm.return_value = mock_llm_instance

    # 3. Repository Instance Mocking
    mock_repo_instance = MockChatRepo.return_value

    return mock_llm_instance, mock_repo_instance

@patch("service.worker_service.ChatRepository")
@patch("service.worker_service.get_llm_service")
@patch("service.worker_service.get_db_conn")
def test_process_sqs_batch_success(mock_get_db_conn, mock_get_llm, MockChatRepo):
    """
    [Scenario 1] 일반 대화 로그 저장 (기존 로직) 테스트
    """
    mock_llm_instance, mock_repo_instance = setup_mocks(mock_get_db_conn, mock_get_llm, MockChatRepo)
    # 임베딩 생성 결과 설정 (1024차원)
    mock_llm_instance.get_embedding.return_value = [0.1] * 1024

    # 테스트 데이터 준비 (일반 로그)
    records = [
        {
            "body": json.dumps({
                "user_id": "user_1",
                "session_id": "session_A",
                "user_input": "안녕하세요",
                "bot_response": {"empathy": "반가워요"}
            })
        }
    ]

    # 실행
    result = process_sqs_batch(records)

    # 검증
    assert result["status"] == "completed"
    assert result["success"] == 1
    assert result["failed"] == 0

    # LLM 임베딩 생성이 호출되었는지
    mock_llm_instance.get_embedding.assert_called_once()
    # DB 저장 함수가 호출되었는지
    mock_repo_instance.log_cbt_session.assert_called_once()

    # 인자 검증
    _, kwargs = mock_repo_instance.log_cbt_session.call_args_list[0]
    assert kwargs["session_id"] == "session_A"


@patch("service.worker_service.ChatRepository")
@patch("service.worker_service.get_llm_service")
@patch("service.worker_service.get_db_conn")
def test_process_sqs_mind_diary_event(mock_get_db_conn, mock_get_llm, MockChatRepo):
    """
    [Scenario 2] 마음일기 연동 메시지 처리 테스트 (실제 데이터 구조 반영)
    """
    mock_llm_instance, mock_repo_instance = setup_mocks(mock_get_db_conn, mock_get_llm, MockChatRepo)

    # LLM 응답 설정 (JSON 문자열)
    mock_llm_response_dict = {
        "empathy": "시험 때문에 많이 속상하셨겠어요.",
        "analysis": "결과에 대한 실망감이 큽니다.",
        "socratic_question": "다음에는 어떻게 준비하면 좋을까요?",
        "detected_distortion": "없음",
        "alternative_thought": "이번 경험이 배움이 될 거예요."
    }
    mock_llm_instance.get_llm_response.return_value = json.dumps(mock_llm_response_dict)

    # [핵심] 실제 마음일기 서비스가 보내는 풀(Full) 데이터 구조 적용
    full_emotion_payload = {
        "top_emotion": "sadness",
        "confidence": 0.85,
        "details": {
            "happy": 0.01,
            "sad": 0.85,
            "angry": 0.05,
            "anxiety": 0.05,
            "neutral": 0.04,
            "surprise": 0.0
        },
        "valence": -0.6,
        "arousal": 0.4
    }

    record = {
        "body": json.dumps({
            "source": "mind-diary",
            "event": "analysis_completed",
            "user_id": "test_user",
            "voice_id": 123,
            "user_name": "홍길동",
            "question": "오늘 가장 아쉬웠던 일은?",
            "content": "열심히 공부했는데 시험을 망쳐서 너무 슬퍼.",
            "recorded_at": "2023-10-25T10:00:00",
            "timestamp": "2023-10-25T10:05:00",
            "emotion": full_emotion_payload  # 상세 감정 데이터 포함
        })
    }

    # 실행
    result = process_sqs_batch([record])

    # 검증
    assert result["success"] == 1

    # LLM 서비스가 호출되었는지 확인
    mock_llm_instance.get_llm_response.assert_called_once()

    # DB 저장 확인
    mock_repo_instance.log_cbt_session.assert_called_once()

    # 저장된 내용 검증
    _, kwargs = mock_repo_instance.log_cbt_session.call_args
    assert kwargs["user_id"] == "test_user"
    assert kwargs["user_input"] == "(마음일기 기반 선제 대화)"
    # 봇 응답의 empathy가 LLM 결과와 일치하는지 확인
    assert kwargs["bot_response"]["empathy"] == "시험 때문에 많이 속상하셨겠어요."


@patch("service.worker_service.ChatRepository")
@patch("service.worker_service.get_llm_service")
@patch("service.worker_service.get_db_conn")
def test_process_sqs_batch_partial_fail(mock_get_db_conn, mock_get_llm, MockChatRepo):
    """[Scenario 3] 에러 처리 테스트"""
    setup_mocks(mock_get_db_conn, mock_get_llm, MockChatRepo)

    records = [
        { "body": "이건 JSON이 아닙니다" }, # 실패 (JSONDecodeError)
        { "body": json.dumps({"user_id": "u2"}) } # 실패 (필수 필드 누락 - 일반 로그 기준)
    ]

    result = process_sqs_batch(records)
    assert result["failed"] == 2
