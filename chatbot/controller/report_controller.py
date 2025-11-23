# chatbot/controller/report_controller.py
from fastapi import APIRouter
from schema.history import WeeklyReportRequest, WeeklyReportResponse
from domain import report_logic

router = APIRouter(tags=["Report"])

@router.post(
    "/chatbot/report/weekly",
    response_model=WeeklyReportResponse,
    summary="주간 마음 소설 생성",
    description="지정된 날짜가 포함된 한 주간의 대화 기록을 분석하여, AI가 작성한 심리 분석 소설(리포트)을 생성하고 반환합니다."
)
def create_weekly_report(request: WeeklyReportRequest):
    return report_logic.generate_weekly_report(request.user_id, request.target_date)
