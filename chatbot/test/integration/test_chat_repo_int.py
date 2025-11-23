import pytest
import uuid
from dependency import get_db_conn
from repository.chat_repository import ChatRepository
import os

# 이 테스트는 'TEST_SCOPE=integration' 일 때만 실행됨
@pytest.mark.skipif(os.environ.get("TEST_SCOPE") != "integration", reason="통합 테스트 환경이 아님")
@pytest.mark.integration
def test_chat_repository_workflow():
    """
    [Integration] 실제 DB에 접속하여 ChatRepository의 동작(저장 -> 조회)을 검증
    """
    # 1. 실제 DB 연결 가져오기
    db_gen = get_db_conn()
    conn = next(db_gen)

    repo = ChatRepository(conn)

    # 테스트용 데이터 생성 (유니크한 ID 사용)
    test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    test_session_id = f"sess_{uuid.uuid4().hex[:6]}"
    test_input = "통합 테스트 중입니다."
    test_response = {"msg": "확인되었습니다."}
    test_embedding = [0.0] * 1024

    try:
        # 2. 저장
        repo.log_cbt_session(
            user_id=test_user_id,
            session_id=test_session_id,
            user_input=test_input,
            bot_response=test_response,
            embedding=test_embedding
        )

        # 3. 조회
        history = repo.get_chat_history(test_session_id, limit=1)

        assert len(history) == 1
        saved_input, saved_response = history[0]

        assert saved_input == test_input
        # JSON 필드는 문자열이나 딕셔너리로 나올 수 있음 (DB 어댑터에 따라 다름)
        if isinstance(saved_response, str):
            import json
            saved_response = json.loads(saved_response)

        assert saved_response["msg"] == "확인되었습니다."

        print(f"\n[SUCCESS] DB 통합 테스트 성공: {test_session_id}")

    except Exception as e:
        pytest.fail(f"DB 통합 테스트 실패: {e}")

    finally:
        # 4. 클린업 : 테스트로 만든 데이터 삭제
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cbt_logs WHERE session_id = %s", (test_session_id,))
            conn.commit()

        # 연결 반납
        try:
            next(db_gen)
        except StopIteration:
            pass
