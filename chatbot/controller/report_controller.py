# chatbot/controller/report_controller.py
from fastapi import APIRouter, Depends
from chatbot.schema.history import WeeklyReportRequest, WeeklyReportResponse
from chatbot.domain.report_logic import ReportService, get_report_service

router = APIRouter(tags=["Report"])

@router.post(
    "/chatbot/report/weekly",
    response_model=WeeklyReportResponse,
    summary="주간 마음 소설 생성",
    description="한 주간의 대화 기록을 분석하여 심리 분석 소설(리포트)을 생성합니다."
)
def create_weekly_report(
        request: WeeklyReportRequest,
        service: ReportService = Depends(get_report_service)
):
    return service.generate_weekly_report(request.user_id, request.target_date)
