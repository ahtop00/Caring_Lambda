# chatbot/controller/dev_controller.py
import json
import boto3
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Depends
from exception import AppError
from config import config
from schema.test import MindDiaryTestRequest, BatchWeeklyReportRequest, BatchWeeklyReportResponse
from schema.reframing import ReframingRequest, ReframingResponse
from service.llm_service import LLMService, get_llm_service
from prompts.reframing import REFRAMING_PROMPT_TEMPLATE
from domain.report_logic import ReportService, get_report_service

logger = logging.getLogger()
router = APIRouter(tags=["Dev / Experiment"])

@router.post(
    "/chatbot/dev/sqs/mind-diary",
    summary="[개발용] 마음일기 분석 완료 이벤트 SQS 전송 테스트",
    description="""
    마음일기 서비스(caring-back)에서 분석이 완료된 상황을 시뮬레이션하여 SQS 메시지를 강제로 전송합니다.
    """
)
def trigger_mind_diary_event(request: MindDiaryTestRequest):
    # 1. 전송할 SQS URL 확인
    sqs_url = config.diary_to_chatbot_sqs_url
    if not sqs_url:
        sqs_url = config.cbt_log_sqs_url # Fallback

    if not sqs_url:
        raise AppError(
            status_code=500,
            message="SQS URL이 설정되지 않았습니다."
        )

    try:
        # 2. SQS 메시지 본문 구성
        message_body = {
            "source": "mind-diary",
            "event": "analysis_completed",
            "user_id": request.user_id,
            "voice_id": 999999, # 테스트용 더미 ID
            "user_name": request.user_name,
            "question": request.question,
            "content": request.content,
            "recorded_at": request.recorded_at or datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "emotion": request.emotion.model_dump()
        }

        # 3. SQS 전송
        sqs_client = boto3.client('sqs', region_name='ap-northeast-2')
        response = sqs_client.send_message(
            QueueUrl=sqs_url,
            MessageBody=json.dumps(message_body, ensure_ascii=False)
        )

        return {
            "success": True,
            "message": "Simulated Mind Diary event sent to SQS",
            "message_id": response.get("MessageId"),
            "payload_preview": message_body
        }

    except Exception as e:
        raise AppError(
            status_code=500,
            message="SQS 메시지 전송에 실패했습니다.",
            detail=str(e)
        )

@router.post(
    "/chatbot/dev/reframing",
    response_model=ReframingResponse,
    summary="[DEV] Gemma 2 리프레이밍 실험",
    description="""
    운영 중인 `/chatbot/reframing` API와 **동일한 입력(Request)과 출력(Response)** 규격을 가집니다.
    내부적으로 DB를 조회하지 않고, **Gemma 2 (Hugging Face)** 모델을 호출하여 답변을 생성합니다.
    
    - **목적**: 기존 모델(Claude/Gemini)과 Gemma 3의 상담 성능 직접 비교 (A/B 테스트)
    - **입력**: ReframingRequest (`user_input` 필수)
    - **출력**: ReframingResponse (공감, 분석, 질문, 대안 등)
    - **제약**: Dev 모드이므로 이전 대화 내역(History)은 반영되지 않습니다.
    """
)
def dev_reframing_gemma(
        request: ReframingRequest,
        service: LLMService = Depends(get_llm_service)
):
    full_prompt = REFRAMING_PROMPT_TEMPLATE.format(
        history_text="(없음. 대화 시작)",
        user_input=request.user_input
    )

    raw_response = service.get_gemma_response(full_prompt)

    try:
        # 마크다운 코드블록 제거 (```json ... ```)
        cleaned_json = raw_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_json)

        return ReframingResponse(
            empathy=data.get("empathy", "공감 내용을 불러오지 못했습니다."),
            detected_distortion=data.get("detected_distortion", "분석 불가"),
            analysis=data.get("analysis", "분석 내용을 생성 중 오류가 발생했습니다."),
            socratic_question=data.get("socratic_question", "질문을 생성하지 못했습니다."),
            alternative_thought=data.get("alternative_thought", "대안을 찾지 못했습니다."),
            emotion=data.get("top_emotion", None) # 감정 필드 추가
        )
    except json.JSONDecodeError:
        logger.error(f"JSON 파싱 실패. 원본 응답: {raw_response}")
        return ReframingResponse(
            empathy=f"[JSON 파싱 실패] 모델 응답: {raw_response}",
            detected_distortion="에러",
            analysis="에러",
            socratic_question="에러",
            alternative_thought="에러"
        )

@router.post(
    "/chatbot/dev/report/weekly/batch",
    response_model=BatchWeeklyReportResponse,
    summary="[스케줄러용] 배치 주간 리포트 생성",
    description="""
    AWS EventBridge 스케줄러에서 호출하는 배치 처리 API입니다.
    
    전주(지난 주)에 해당하는 기간에 cbt_logs에 데이터가 있는 모든 사용자에 대해 주간 리포트를 생성합니다.
    (월요일에 실행되면 그 전주 리포트를 생성)
    
    **동작 방식:**
    1. `target_date`를 기준으로 전주(지난 주)의 시작일(월요일)~종료일(일요일)을 계산
    2. 해당 기간에 cbt_logs에 데이터가 있는 모든 user_id 조회
    3. 각 사용자별로 `/chatbot/report/weekly`와 동일한 로직으로 리포트 생성
    4. 생성 결과(성공/실패)를 집계하여 반환
    
    **예시:**
    - 월요일(2025-11-24)에 실행 → 전주(2025-11-17 ~ 2025-11-23) 리포트 생성
    
    **주의사항:**
    - 이미 해당 주에 리포트가 생성된 사용자는 중복 생성될 수 있습니다.
    - LLM 호출이 많아 처리 시간이 오래 걸릴 수 있습니다.
    """
)
def batch_weekly_report(
        request: BatchWeeklyReportRequest,
        service: ReportService = Depends(get_report_service)
):
    """배치 주간 리포트 생성 엔드포인트"""
    start_time = time.time()
    # Lambda 최대 타임아웃: 15분 (900초), 안전 마진: 30초
    MAX_EXECUTION_TIME = 870  # 14분 30초
    
    logger.info(f"배치 주간 리포트 생성 요청 시작 - target_date: {request.target_date}")
    
    try:
        result = service.generate_weekly_reports_for_period(
            request.target_date, 
            start_time=start_time,
            max_execution_time=MAX_EXECUTION_TIME
        )
        elapsed_time = time.time() - start_time
        logger.info(
            f"배치 주간 리포트 생성 완료 - period: {result['period']}, "
            f"성공: {result['success_count']}, 실패: {result['failed_count']}, 스킵: {result['skipped_count']}, "
            f"타임아웃: {result['is_timeout']}, 미처리: {result['remaining_users']}, "
            f"소요 시간: {elapsed_time:.1f}초"
        )
        return result
    except Exception as e:
        logger.error(f"배치 주간 리포트 생성 실패 - target_date: {request.target_date}, error: {e}", exc_info=True)
        raise
