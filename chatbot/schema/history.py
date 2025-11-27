# chatbot/schema/history.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, date

# --- 채팅방 목록 (Session List) ---
class ChatSessionItem(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    last_message: str = Field(..., description="마지막 대화 내용 (미리보기)")
    last_updated: datetime = Field(..., description="마지막 대화 시각")
    distortion_tags: List[str] = Field(default=[], description="이 방에서 감지된 주요 왜곡 태그")
    emotion: Optional[str] = Field(
        None,
        description="해당 세션의 마지막 대화에서 분석된 감정 (예: anxiety, happy)"
    )

class SessionListResponse(BaseModel):
    sessions: List[ChatSessionItem]

# --- 채팅 상세 내역 (Chat History) ---
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' 또는 'assistant'")
    content: str = Field(..., description="대화 내용")
    timestamp: datetime
    # 봇 응답일 경우 추가 정보
    detected_distortion: Optional[str] = Field(
        None,
        description="탐지된 인지 왜곡 유형"
    )
    empathy: Optional[str] = Field(None, description="공감 문장")
    analysis: Optional[str] = Field(None, description="인지 왜곡 분석 설명")
    socratic_question: Optional[str] = Field(None, description="소크라테스식 질문")
    alternative_thought: Optional[str] = Field(None, description="대안적 사고 제안")
    emotion: Optional[str] = Field(None, description="감정 라벨")
    # 음성 파일 URL (사용자 메시지인 경우)
    s3_url: Optional[str] = Field(None, description="업로드된 음성 파일 URL")

class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    total_page: int
    current_page: int

# --- 주간 리포트 (Weekly Report) ---
class WeeklyReportRequest(BaseModel):
    user_id: str = Field(..., description="사용자 ID")
    target_date: date = Field(..., description="조회하려는 날짜 (YYYY-MM-DD, 해당 날짜가 포함된 주를 분석)")

class WeeklyReportResponse(BaseModel):
    report_id: int
    title: str
    content: str
    period: str
    emotions: Dict[str, int]

# --- 월별 리포트 조회 ---
class WeeklyReportItem(BaseModel):
    report_id: int
    title: str = Field(..., description="소설 제목")
    content: str = Field(..., description="소설 본문")
    period: str = Field(..., description="분석 기간 (YYYY-MM-DD ~ YYYY-MM-DD)")
    emotions: Dict[str, int] = Field(..., description="감정 통계")
    created_at: date = Field(..., description="리포트 생성일(주간 시작일 기준)")

class MonthlyReportListResponse(BaseModel):
    year: int
    month: int
    reports: List[WeeklyReportItem]
