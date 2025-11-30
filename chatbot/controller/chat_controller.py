import logging
from fastapi import APIRouter, Query, Depends
from schema.reframing import ReframingRequest, ReframingResponse, VoiceReframingRequest
from schema.history import SessionListResponse, ChatHistoryResponse
from domain.reframing_logic import ReframingService, get_reframing_service
from domain.chat_logic import ChatService, get_chat_service
from schema.common import COMMON_RESPONSES

logger = logging.getLogger()
router = APIRouter(tags=["CBT Reframing"])

@router.post(
    "/chatbot/reframing",
    response_model=ReframingResponse,
    summary="CBT 리프레이밍 상담",
    description="""
    사용자의 고민을 입력받아 CBT 기반의 상담을 제공합니다.
    
    **[처리 과정]**
    1. **공감**: 감정 파악 및 위로
    2. **왜곡 탐지**: 인지적 오류(흑백논리 등) 분석
    3. **질문/대안**: 소크라테스식 질문 제공
    4. **로그 저장**: 분석용 데이터 SQS 비동기 전송

    ---
    ### 📝 Swagger 테스트 가이드 (필독)
    대화의 **맥락(Context)을 유지**하며 테스트하려면 아래 규칙을 지켜주세요.

    1. **`session_id` (필수)**: 
       - **랜덤한 6자리 영문+숫자** 조합으로 직접 입력해주세요. (예: `A1B2C3`, `KD83SA`)
       - 이 ID가 같아야 **'하나의 대화 스레드'**로 인식되어 이전 대화 기억을 불러옵니다.
    
    2. **`user_id` (필수)**:
       - 테스트하는 동안 **동일한 ID**를 사용하세요. (예: `test_user_1`)
       - `user_id`와 `session_id`가 모두 일치해야 이전 턴의 대화 내용을 기억합니다.
    
    3. **새로운 상담 시작**:
       - 대화 주제를 바꾸고 싶다면 `session_id`를 새로운 값(예: `NEW001`)으로 변경해서 요청하세요.
    """,
    responses=COMMON_RESPONSES
)
def reframing_endpoint(
        request: ReframingRequest,
        service: ReframingService = Depends(get_reframing_service)
):
    """텍스트 기반 상담 엔드포인트"""
    logger.info(
        f"리프레이밍 요청 시작 - user_id: {request.user_id}, session_id: {request.session_id}"
    )
    try:
        result = service.execute_reframing(request)
        logger.info(f"리프레이밍 요청 완료 - user_id: {request.user_id}, session_id: {request.session_id}")
        return result
    except Exception as e:
        logger.error(
            f"리프레이밍 요청 실패 - user_id: {request.user_id}, "
            f"session_id: {request.session_id}, error: {e}",
            exc_info=True
        )
        raise

@router.post(
    "/chatbot/voice-reframing",
    response_model=ReframingResponse,
    summary="음성 기반 상담 (감정 데이터 포함)",
    description="caring-back에서 분석된 음성 감정 데이터를 포함하여 상담을 진행합니다."
)
def voice_reframing_endpoint(
        request: VoiceReframingRequest,
        service: ReframingService = Depends(get_reframing_service)
):
    """음성 기반 상담 엔드포인트"""
    logger.info(
        f"음성 리프레이밍 요청 시작 - user_id: {request.user_id}, "
        f"session_id: {request.session_id}, emotion: {request.emotion.get('top_emotion', 'N/A')}"
    )
    try:
        result = service.execute_voice_reframing(request)
        logger.info(f"음성 리프레이밍 요청 완료 - user_id: {request.user_id}, session_id: {request.session_id}")
        return result
    except Exception as e:
        logger.error(
            f"음성 리프레이밍 요청 실패 - user_id: {request.user_id}, "
            f"session_id: {request.session_id}, error: {e}",
            exc_info=True
        )
        raise

@router.get(
    "/chatbot/sessions",
    response_model=SessionListResponse,
    summary="채팅방 목록 조회",
    description="사용자의 과거 상담 채팅방 목록을 최신순으로 반환합니다.",
    responses=COMMON_RESPONSES
)
def get_sessions(
        user_id: str,
        service: ChatService = Depends(get_chat_service)
):
    """채팅방 목록 조회 엔드포인트"""
    logger.info(f"채팅방 목록 조회 요청 - user_id: {user_id}")
    try:
        result = service.get_user_sessions(user_id)
        logger.info(f"채팅방 목록 조회 완료 - user_id: {user_id}, count: {len(result.sessions)}")
        return result
    except Exception as e:
        logger.error(f"채팅방 목록 조회 실패 - user_id: {user_id}, error: {e}", exc_info=True)
        raise

@router.get(
    "/chatbot/history/{session_id}",
    response_model=ChatHistoryResponse,
    summary="채팅 상세 조회",
    description="특정 세션의 대화 내용을 페이징하여 반환합니다.",
    responses=COMMON_RESPONSES
)
def get_history(
        session_id: str,
        page: int = Query(1, ge=1),
        service: ChatService = Depends(get_chat_service)
):
    """채팅 상세 조회 엔드포인트"""
    logger.info(f"채팅 상세 조회 요청 - session_id: {session_id}, page: {page}")
    try:
        result = service.get_session_history(session_id, page)
        logger.info(f"채팅 상세 조회 완료 - session_id: {session_id}, messages: {len(result.messages)}")
        return result
    except Exception as e:
        logger.error(f"채팅 상세 조회 실패 - session_id: {session_id}, page: {page}, error: {e}", exc_info=True)
        raise
