# chatbot/schema/history.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date

# --- 채팅방 목록 (Session List) ---
class ChatSessionItem(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    last_message: str = Field(..., description="마지막 대화 내용 (미리보기)")
    last_updated: datetime = Field(..., description="마지막 대화 시각")
    distortion_tags: List[str] = Field(default=[], description="이 방에서 감지된 주요 왜곡 태그")

class SessionListResponse(BaseModel):
    sessions: List[ChatSessionItem]

# --- 채팅 상세 내역 (Chat History) ---
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' 또는 'assistant'")
    content: str = Field(..., description="대화 내용")
    timestamp: datetime
    # 봇 응답일 경우 추가 정보
    distortion: Optional[str] = None
    empathy: Optional[str] = None

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
