# chatbot/controller/test_controller.py
import json
import boto3
from datetime import datetime
from fastapi import APIRouter, Depends

from exception import AppError
from config import config

from schema.test import MindDiaryTestRequest
from schema.reframing import ReframingRequest, ReframingResponse
from service.llm_service import LLMService, get_llm_service
from prompts.reframing import REFRAMING_PROMPT_TEMPLATE

router = APIRouter(tags=["Dev Test"])

@router.post(
    "/chatbot/test/sqs/mind-diary",
    summary="[개발용] 마음일기 분석 완료 이벤트 SQS 전송 테스트",
    description="""
    마음일기 서비스(caring-back)에서 분석이 완료된 상황을 시뮬레이션하여 SQS 메시지를 강제로 전송합니다.
    
    - **목적**: 챗봇의 '선제적 대화(Proactive Message)' 생성 로직 검증
    - **동작**: 입력받은 데이터를 SQS(`diary-to-chatbot-sqs`)로 전송 -> 챗봇 Worker Lambda 트리거 -> DB에 대화 생성
    - **테스트 확인**: 요청(request)시에 보낸 user_id를 이용해서 리스트를 검색해보세요. ai 분석이 끝나는 대로 새로운 대화가 확인 가능합니다.  
    - **이후 대화**: 처음 대화 이후에 이어나가고 싶으면 기존 CBT 질문 API를 활용 해주세요.
    """
)
def trigger_mind_diary_event(request: MindDiaryTestRequest):
    # 1. 전송할 SQS URL 확인 (Config 객체 사용)
    sqs_url = config.diary_to_chatbot_sqs_url

    # [Fallback] 전용 큐 설정이 없다면 기존 로그 큐 사용 (테스트 편의성)
    if not sqs_url:
        sqs_url = config.cbt_log_sqs_url

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
    summary="[개발용] Gemma 3 리프레이밍 실험",
    description="""
    운영 중인 리프레이밍 API와 **동일한 입력(Request)**을 받아, 
    **Hugging Face Endpoint(Gemma 3)** 모델을 통해 답변을 생성합니다.
    
    - **목적**: 기존 모델(Claude/Gemini)과 Gemma 3의 상담 성능 비교 (A/B 테스트)
    - **입력**: ReframingRequest (운영 API와 동일)
    - **출력**: ReframingResponse (운영 API와 동일)
    - **참고**: Dev 모드이므로 이전 대화 내역(History)은 비워둔 상태로 1회성 답변만 테스트합니다.
    """
)
def test_reframing_gemma(
        request: ReframingRequest,
        service: LLMService = Depends(get_llm_service)
):
    full_prompt = REFRAMING_PROMPT_TEMPLATE.format(
        history_text="(없음. 대화 시작)",
        user_input=request.content
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
            alternative_thought=data.get("alternative_thought", "대안을 찾지 못했습니다.")
        )
    except json.JSONDecodeError:
        return ReframingResponse(
            empathy=f"[JSON 파싱 실패] 모델 응답: {raw_response}",
            detected_distortion="에러",
            analysis="에러",
            socratic_question="에러",
            alternative_thought="에러"
        )
