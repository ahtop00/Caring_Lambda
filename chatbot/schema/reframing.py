# chatbot/schema/reframing.py
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# =============================================================================
# Hume AI 감정 분석 데이터 스키마
# =============================================================================

class EmotionScore(BaseModel):
    """개별 감정 score"""
    name: str = Field(..., description="Hume 감정명 (예: Sadness, Joy)")
    score: float = Field(..., description="감정 점수 (0.000 ~ 1.000)")


class TimeRange(BaseModel):
    """시간 구간"""
    begin: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")


class TextPosition(BaseModel):
    """텍스트 내 문자 위치"""
    begin: int = Field(..., description="시작 위치 (문자 인덱스)")
    end: int = Field(..., description="종료 위치 (문자 인덱스)")


class ProsodyUtterance(BaseModel):
    """Prosody 모델 발화 단위 분석 결과"""
    text: str = Field(..., description="발화 텍스트 (Hume STT)")
    time: TimeRange = Field(..., description="시간 구간")
    confidence: float = Field(0.0, description="STT 신뢰도 (0~1)")
    top_emotions: List[EmotionScore] = Field(default_factory=list, description="상위 감정 (최대 3개)")


class HumeProsody(BaseModel):
    """Prosody 모델 분석 결과 (음성 톤, 리듬, 음색)"""
    summary: List[EmotionScore] = Field(default_factory=list, description="전체 감정 평균 상위 10개")
    utterances: List[ProsodyUtterance] = Field(default_factory=list, description="발화 단위 분석")


class BurstEvent(BaseModel):
    """Burst 모델 이벤트"""
    time: TimeRange = Field(..., description="시간 구간")
    description: str = Field("", description="소리 종류 (sigh, laugh, gasp 등)")
    top_emotions: List[EmotionScore] = Field(default_factory=list, description="상위 감정 (최대 3개)")


class HumeBurst(BaseModel):
    """Burst 모델 분석 결과 (비언어적 소리)"""
    summary: List[EmotionScore] = Field(default_factory=list, description="전체 감정 평균 상위 5개")
    events: List[BurstEvent] = Field(default_factory=list, description="감지된 비언어적 소리")


class SentimentDistItem(BaseModel):
    """Sentiment 분포 항목"""
    name: str = Field(..., description="점수 (1~9 문자열)")
    score: float = Field(..., description="확률")


class SentimentData(BaseModel):
    """Sentiment 분석 결과"""
    distribution: List[SentimentDistItem] = Field(default_factory=list, description="1~9점 확률 분포")
    dominant: int = Field(5, description="최빈 sentiment 점수 (1~9)")
    weighted_mean: float = Field(5.0, description="가중 평균 (1.0~9.0)")


class LanguageUtterance(BaseModel):
    """Language 모델 발화 단위 분석 결과"""
    text: str = Field(..., description="발화 텍스트")
    position: Optional[TextPosition] = Field(None, description="텍스트 내 문자 위치")
    top_emotions: List[EmotionScore] = Field(default_factory=list, description="상위 감정 (최대 3개)")
    sentiment_dominant: Optional[int] = Field(None, description="해당 발화의 최빈 sentiment (1~9)")


class HumeLanguage(BaseModel):
    """Language 모델 분석 결과 (텍스트 의미와 어조)"""
    summary: List[EmotionScore] = Field(default_factory=list, description="전체 감정 평균 상위 10개")
    sentiment: Optional[SentimentData] = Field(None, description="감정 극성 분석")
    toxicity: List[EmotionScore] = Field(default_factory=list, description="독성 분석 6개 카테고리")
    utterances: List[LanguageUtterance] = Field(default_factory=list, description="발화 단위 분석")


class EmotionAnalysis(BaseModel):
    """Hume AI 감정 분석 결과 (Spring이 가공하여 전달)"""
    source: str = Field("hume", description="분석 소스 ('hume' 고정)")
    prosody: Optional[HumeProsody] = Field(None, description="음성 톤 분석")
    burst: Optional[HumeBurst] = Field(None, description="비언어적 소리 분석")
    language: Optional[HumeLanguage] = Field(None, description="텍스트 의미 분석")


class EmotionResult(BaseModel):
    """Lambda가 매핑한 감정 분류 결과"""
    primary_category: str = Field(..., description="1차 감정 (한국어: 기쁨/슬픔/불안/분노/놀람/평온)")
    secondary_category: Optional[str] = Field(None, description="2차 감정 (primary와 score 차이 0.2 이내)")
    primary_emotions: List[EmotionScore] = Field(default_factory=list, description="Hume 세부 감정 상위 3개")
    sentiment_summary: Optional[float] = Field(None, description="sentiment 가중 평균 (1.0~9.0)")


# =============================================================================
# 요청 (Request)
# =============================================================================

class ReframingRequest(BaseModel):
    """텍스트 상담 요청 (기존 호환 유지)"""
    user_id: str = Field(..., description="사용자 식별 ID")
    session_id: str = Field(..., description="대화 스레드 ID (랜덤 6자리)")
    user_input: str = Field(..., description="현재 사용자의 발화")
    emotion: Optional[str] = Field(
        None,
        description="감정 힌트 (happy, sad, neutral, angry, anxiety, surprise). 제공 시 감정 맞춤 CBT 전략이 적용됩니다."
    )


class VoiceReframingRequest(BaseModel):
    """음성 상담 요청 (Hume AI 연동)"""
    user_id: str = Field(..., description="사용자 식별 ID")
    session_id: str = Field(..., description="대화 스레드 ID (랜덤 6자리)")
    user_input: str = Field(..., description="현재 사용자의 발화, STT 결과")

    # Hume AI 감정 분석 결과 (신규)
    emotion_analysis: Optional[EmotionAnalysis] = Field(
        None,
        description="Hume AI 감정 분석 결과. Spring이 가공하여 전달. Hume 실패 시 null"
    )

    # 기존 필드 (하위 호환용 — emotion_analysis가 있으면 무시됨)
    emotion: Optional[Dict[str, Any]] = Field(
        None,
        description="[deprecated] 기존 감정 분석 결과. emotion_analysis 우선 사용"
    )

    user_name: Optional[str] = Field("내담자", description="사용자 이름")
    s3_url: Optional[str] = Field(None, description="업로드된 음성 파일의 S3 URL")


# =============================================================================
# 응답 (Response)
# =============================================================================

class ReframingResponse(BaseModel):
    """상담 응답 (텍스트/음성 공통)"""
    empathy: str = Field(..., description="사용자의 감정에 대한 공감")
    detected_distortion: str = Field(..., description="탐지된 인지 왜곡 유형")
    analysis: str = Field(..., description="왜곡 분석 및 설명")
    socratic_question: str = Field(..., description="스스로 깨닫게 하는 질문")
    alternative_thought: str = Field(..., description="균형 잡힌 대안적 사고")
    emotion: Optional[str] = Field(
        None,
        description="핵심 감정 (happy, sad, neutral, angry, anxiety, surprise)"
    )

    # Hume 매핑 결과 (신규)
    emotion_result: Optional[EmotionResult] = Field(
        None,
        description="Hume AI 감정 매핑 결과. 텍스트 모드에서는 자체 분석 결과"
    )
