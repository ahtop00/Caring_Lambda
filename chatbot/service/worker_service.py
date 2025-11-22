# chatbot/service/worker_service.py
import json
import logging
from service import llm_service, db_service

logger = logging.getLogger()

def process_sqs_batch(records: list) -> dict:
    """
    SQS 레코드 배치(Batch)를 처리하는 비즈니스 로직
    """
    logger.info(f"SQS 백그라운드 작업 시작: {len(records)}건")

    success_count = 0
    failed_count = 0

    for record in records:
        try:
            # 메시지 본문 파싱
            # (SQS 메시지 body가 문자열이므로 JSON 로드 필요)
            payload = json.loads(record['body'])

            user_id = payload.get('user_id')
            session_id = payload.get('session_id')
            user_input = payload.get('user_input')
            bot_response = payload.get('bot_response')

            # 필수 필드 검증
            if not all([user_id, session_id, user_input]):
                logger.warning(f"필수 필드 누락으로 스킵: {payload}")
                failed_count += 1
                continue

            logger.info(f"로그 저장 작업 처리 중 (Session: {session_id})")

            # [작업 A] Titan 임베딩 생성
            try:
                embedding = llm_service.get_embedding(user_input)
            except Exception as e:
                logger.error(f"임베딩 생성 실패 (Session: {session_id}): {e}")
                embedding = [0.0] * 1024 # 실패 시 0 벡터 처리

            # [작업 B] DB 저장
            db_service.log_cbt_session(
                user_id=user_id,
                session_id=session_id,
                user_input=user_input,
                bot_response=bot_response,
                embedding=embedding
            )

            success_count += 1

        except json.JSONDecodeError:
            logger.error(f"SQS Body 파싱 실패: {record.get('body')}")
            failed_count += 1
        except Exception as e:
            logger.error(f"SQS 메시지 처리 중 알 수 없는 오류: {e}")
            failed_count += 1
            # 필요 시 raise하여 SQS 재시도 유발 가능 (여기선 로그만 남김)

    logger.info(f"SQS 배치 처리 완료 (성공: {success_count}, 실패: {failed_count})")

    return {
        "status": "completed",
        "processed": len(records),
        "success": success_count,
        "failed": failed_count
    }
