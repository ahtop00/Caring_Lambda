# chatbot/controller/dev_controller.py
import json
import boto3
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from exception import AppError
from config import config
from schema.test import MindDiaryTestRequest
from schema.reframing import ReframingRequest, ReframingResponse
from service.llm_service import LLMService, get_llm_service
from prompts.reframing import REFRAMING_PROMPT_TEMPLATE

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
    summary="[DEV] Gemma 2 리프레이밍 실험 (Fine-tuned)",
    description="""
    Fine-tuning된 Gemma 2 모델을 사용합니다.
    복잡한 프롬프트 없이 사용자 입력(User Input)만 전달하여 모델 자체의 학습된 능력으로 답변을 생성합니다.
    """
)
def dev_reframing_gemma(
        request: ReframingRequest,
        service: LLMService = Depends(get_llm_service)
):
    # [변경 사항]
    # 거대한 REFRAMING_PROMPT_TEMPLATE과 .format() 과정을 제거했습니다.
    # 학습된 모델이므로 사용자 입력 텍스트만 그대로 전달합니다.

    # 만약 학습 데이터가 "User: {text}" 형태였다면 그 형식을 맞춰줘야 할 수도 있습니다.
    # 여기서는 가장 순수한 형태인 입력값 자체를 전달합니다.
    input_text = request.user_input

    # 서비스 호출 (이제 input_text는 수십 토큰 수준으로 매우 짧아집니다)
    raw_response = service.get_gemma_response(input_text)

    try:
        # Gemma 3가 JSON 외에 잡담을 섞는 경우를 대비한 클리닝 (기존 로직 유지)
        cleaned_json = raw_response.replace("``````", "").strip()

        # 혹시 모델이 JSON만 뱉지 않고 앞뒤로 사족을 달 경우를 대비해
        # '{' 로 시작해서 '}' 로 끝나는 부분만 추출하는 로직을 추가하면 더 안전합니다.
        if "{" in cleaned_json and "}" in cleaned_json:
            start_idx = cleaned_json.find("{")
            end_idx = cleaned_json.rfind("}") + 1
            cleaned_json = cleaned_json[start_idx:end_idx]

        data = json.loads(cleaned_json)

        return ReframingResponse(
            empathy=data.get("empathy", "공감 내용을 불러오지 못했습니다."),
            detected_distortion=data.get("detected_distortion", "분석 불가"),
            analysis=data.get("analysis", "분석 내용을 생성 중 오류가 발생했습니다."),
            socratic_question=data.get("socratic_question", "질문을 생성하지 못했습니다."),
            alternative_thought=data.get("alternative_thought", "대안을 찾지 못했습니다."),
            emotion=data.get("top_emotion", None) or data.get("emotion", None)
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
