# chatbot/schema/test.py
from pydantic import BaseModel, Field
from typing import Optional

class EmotionDetail(BaseModel):
    """감정별 세부 점수 (0.0 ~ 1.0)"""
    happy: float = Field(0.0, description="기쁨/행복 (0.0~1.0)")
    sad: float = Field(0.0, description="슬픔 (0.0~1.0)")
    angry: float = Field(0.0, description="분노 (0.0~1.0)")
    anxiety: float = Field(0.0, description="불안/공포 (0.0~1.0)")
    neutral: float = Field(0.0, description="중립 (0.0~1.0)")
    surprise: float = Field(0.0, description="놀람/당황 (0.0~1.0)")

class EmotionPayload(BaseModel):
    """감정 분석 결과 페이로드"""
    top_emotion: str = Field(..., description="가장 지배적인 대표 감정 (예: anxiety, sad, happy)")
    confidence: float = Field(..., description="대표 감정의 신뢰도 (0.0 ~ 1.0)")
    details: EmotionDetail = Field(..., description="6가지 감정별 상세 점수")
    valence: float = Field(0.0, description="긍정/부정 수치 (-1.0 ~ 1.0)")
    arousal: float = Field(0.0, description="각성/흥분 정도 (0.0 ~ 1.0)")

class MindDiaryTestRequest(BaseModel):
    """마음일기 SQS 이벤트 시뮬레이션 요청 DTO"""
    user_id: str = Field(..., description="사용자 아이디 (DB의 username)")
    user_name: str = Field(default="테스트유저", description="사용자 이름 (챗봇이 불러줄 호칭)")
    question: str = Field(default="오늘 하루는 어땠나요?", description="일기 주제/질문")
    content: str = Field(..., description="사용자가 작성한 일기 내용 (텍스트)")
    recorded_at: Optional[str] = Field(None, description="녹음/작성 일시 (ISO 8601 형식, 미입력시 현재시간)")
    emotion: EmotionPayload = Field(..., description="감정 분석 결과 데이터")

    # Swagger 예시 데이터 설정
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "test_user_123",
                "user_name": "김철수",
                "question": "오늘 가장 기억에 남는 순간은 언제였나요?",
                "content": "오늘 회사에서 큰 프로젝트 발표를 마쳤어. 실수할까 봐 너무 떨리고 불안했는데, 다행히 팀장님이 칭찬해 주셔서 안심이 됐어. 하지만 아직도 긴장이 다 풀리지 않아서 좀 피곤해.",
                "recorded_at": "2025-11-24T18:30:00",
                "emotion": {
                    "top_emotion": "anxiety",
                    "confidence": 0.65,
                    "valence": 0.2,
                    "arousal": 0.6,
                    "details": {
                        "happy": 0.15,
                        "sad": 0.05,
                        "angry": 0.0,
                        "anxiety": 0.65,
                        "neutral": 0.1,
                        "surprise": 0.05
                    }
                }
            }
        }
    }
