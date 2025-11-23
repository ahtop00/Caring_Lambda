# chatbot/service/worker_service.py
import json
import logging
import secrets
import string
from datetime import datetime

from dependency import get_db_conn
from service.llm_service import get_llm_service
from repository.chat_repository import ChatRepository
from prompts.mind_diary import get_mind_diary_prompt
from util.json_parser import parse_llm_json

logger = logging.getLogger()

def process_sqs_batch(records: list) -> dict:
    """
    SQS 레코드 배치(Batch)를 처리하는 비즈니스 로직
    (FastAPI 밖에서 실행되므로 의존성을 수동으로 주입합니다)
    """
    logger.info(f"SQS 백그라운드 작업 시작: {len(records)}건")

    db_gen = get_db_conn()
    conn = next(db_gen)

    try:
        chat_repo = ChatRepository(conn)
        llm_service = get_llm_service() # Singleton 인스턴스

        success_count = 0
        failed_count = 0

        for record in records:
            try:
                payload = json.loads(record['body'])
                source = payload.get("source")

                is_success = False

                if source == "mind-diary":
                    # Case A: 마음일기 분석 완료 -> 선제적 대화 생성
                    is_success = _handle_mind_diary_event(payload, chat_repo, llm_service)
                else:
                    # Case B: 일반 대화 로그 저장
                    is_success = _handle_log_archiving(payload, chat_repo, llm_service)

                if is_success:
                    success_count += 1
                else:
                    failed_count += 1

            except json.JSONDecodeError:
                logger.error(f"SQS Body 파싱 실패: {record.get('body')}")
                failed_count += 1
            except Exception as e:
                logger.error(f"SQS 메시지 처리 중 알 수 없는 오류: {e}", exc_info=True)
                failed_count += 1

        logger.info(f"SQS 배치 처리 완료 (성공: {success_count}, 실패: {failed_count})")

        return {
            "status": "completed",
            "processed": len(records),
            "success": success_count,
            "failed": failed_count
        }

    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

def _handle_log_archiving(payload: dict, repo: ChatRepository, llm) -> bool:
    """
    기존 대화 로그 저장 로직
    Returns:
        bool: 성공 시 True, 실패(필수값 누락 등) 시 False
    """
    try:
        user_id = payload.get('user_id')
        session_id = payload.get('session_id')
        user_input = payload.get('user_input')
        bot_response = payload.get('bot_response')

        # 필수 필드 검증
        if not all([user_id, session_id, user_input]):
            logger.warning(f"필수 필드 누락으로 로그 저장 스킵: {payload}")
            return False

        logger.info(f"로그 저장 작업 처리 중 (Session: {session_id})")

        # Titan 임베딩 생성
        embedding = [0.0] * 1024
        try:
            embedding = llm.get_embedding(user_input)
        except Exception as e:
            logger.error(f"임베딩 생성 실패 (Session: {session_id}): {e}")

        # DB 저장
        repo.log_cbt_session(
            user_id=user_id,
            session_id=session_id,
            user_input=user_input,
            bot_response=bot_response,
            embedding=embedding
        )
        return True

    except Exception as e:
        logger.error(f"로그 저장 중 오류 발생: {e}")
        return False

def _handle_mind_diary_event(payload: dict, repo: ChatRepository, llm) -> bool:
    """
    마음일기 데이터를 바탕으로 챗봇이 먼저 말을 거는 로직
    Returns:
        bool: 성공 시 True, 실패 시 False
    """
    try:
        # 데이터 추출
        user_id = payload.get('user_id')
        user_name = payload.get('user_name', '사용자')
        question = payload.get('question', '(자유 일기)')
        content = payload.get('content')
        recorded_at = payload.get('recorded_at', '알 수 없음')

        # 필수 데이터 확인
        if not user_id or not content:
            logger.warning(f"마음일기 필수 필드 누락: {payload}")
            return False

        # 감정 데이터 추출
        emotion_data = payload.get('emotion', {})
        top_emotion = emotion_data.get('top_emotion', 'neutral')
        emotion_details = emotion_data.get('details', {}) # 세부 감정 수치

        logger.info(f"마음일기 연동 시작: user={user_id}, emotion={top_emotion}")

        # 프롬프트 생성 (세부 감정 전달)
        prompt = get_mind_diary_prompt(
            user_name=user_name,
            question=question,
            content=content,
            top_emotion=top_emotion,
            emotion_details=emotion_details,
            recorded_at=recorded_at
        )

        # LLM 응답 생성 (첫 마디)
        llm_raw_response = llm.get_llm_response(prompt, use_bedrock=False)

        # JSON 파싱 (유틸리티 사용)
        try:
            bot_response_dict = parse_llm_json(llm_raw_response)
        except ValueError:
            logger.warning("마음일기 LLM 파싱 실패 -> Fallback")
            bot_response_dict = {
                "empathy": llm_raw_response,
                "detected_distortion": "분석 불가",
                "analysis": "내용을 불러오지 못했습니다.",
                "socratic_question": "오늘 하루는 어떠셨나요?",
                "alternative_thought": "항상 응원합니다."
            }

        # 새로운 세션 ID 생성 (대문자+숫자 6자리)
        alphabet = string.ascii_uppercase + string.digits
        new_session_id = ''.join(secrets.choice(alphabet) for _ in range(6))

        # 응답 포맷 정리
        final_bot_response = {
            "empathy": bot_response_dict.get("empathy", ""),
            "detected_distortion": bot_response_dict.get("detected_distortion", "MindDiary"),
            "analysis": bot_response_dict.get("analysis", ""),
            "socratic_question": bot_response_dict.get("socratic_question", ""),
            "alternative_thought": bot_response_dict.get("alternative_thought", "")
        }

        # DB 저장
        repo.log_cbt_session(
            user_id=user_id,
            session_id=new_session_id,
            user_input="(마음일기 기반 선제 대화)", # 식별용 마커
            bot_response=final_bot_response,
            embedding=[0.0] * 1024
        )

        logger.info(f"선제 대화 생성 완료: session_id={new_session_id}")
        return True

    except Exception as e:
        logger.error(f"마음일기 처리 중 오류 발생: {e}", exc_info=True)
        return False
