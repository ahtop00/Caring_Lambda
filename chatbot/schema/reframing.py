# chatbot/schema/reframing.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

# --- 요청 (Request) ---
class ReframingRequest(BaseModel):
    user_id: str = Field(..., description="사용자 식별 ID")
    session_id: str = Field(..., description="대화 스레드 ID (랜덤 6자리)")
    user_input: str = Field(..., description="현재 사용자의 발화")

# --- 응답 (Response) ---
class ReframingResponse(BaseModel):
    empathy: str = Field(..., description="사용자의 감정에 대한 공감")
    detected_distortion: str = Field(..., description="탐지된 인지 왜곡 유형")
    analysis: str = Field(..., description="왜곡 분석 및 설명")
    socratic_question: str = Field(..., description="스스로 깨닫게 하는 질문")
    alternative_thought: str = Field(..., description="균형 잡힌 대안적 사고")
    emotion: Optional[str] = Field(
        None,
        description="핵심 감정 (happy, sad, neutral, angry, anxiety, surprise)"
    )

class VoiceReframingRequest(BaseModel):
    user_id: str = Field(..., description="사용자 식별 ID")
    session_id: str = Field(..., description="대화 스레드 ID (랜덤 6자리)")
    user_input: str = Field(..., description="현재 사용자의 발화, STT 결과")

    emotion: Dict[str, Any] = Field(
        ...,
        description="감정 분석 결과 (예: {'valence': 0.8, 'arousal': 0.5, 'top_emotion': 'happy'})"
    )
    user_name: Optional[str] = "내담자"
    s3_url: Optional[str] = Field(None, description="업로드된 음성 파일의 S3 URL")
