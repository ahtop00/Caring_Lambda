# chatbot/controller/report_controller.py
from fastapi import APIRouter, Depends, Query
from schema.history import WeeklyReportRequest, WeeklyReportResponse, MonthlyReportListResponse
from domain.report_logic import ReportService, get_report_service
from schema.common import COMMON_RESPONSES

router = APIRouter(tags=["Report"])

@router.post(
    "/chatbot/report/weekly",
    response_model=WeeklyReportResponse,
    summary="주간 마음 소설 생성",
    description="한 주간의 대화 기록을 분석하여 심리 분석 소설(리포트)을 생성합니다.",
    responses=COMMON_RESPONSES
)
def create_weekly_report(
        request: WeeklyReportRequest,
        service: ReportService = Depends(get_report_service)
):
    return service.generate_weekly_report(request.user_id, request.target_date)

@router.get(
    "/chatbot/report/monthly",
    response_model=MonthlyReportListResponse,
    summary="월별 주간 리포트 모아보기",
    description="""
    특정 연도(year)와 월(month)에 생성된 모든 주간 리포트를 조회합니다.
    백엔드에서 이미 생성된 데이터를 가져오므로 별도의 생성 대기 시간이 없습니다.
    """,
    responses=COMMON_RESPONSES
)
def get_monthly_reports(
        user_id: str = Query(..., description="사용자 ID"),
        year: int = Query(..., description="조회할 연도 (예: 2025)"),
        month: int = Query(..., ge=1, le=12, description="조회할 월 (1~12)"),
        service: ReportService = Depends(get_report_service)
):
    return service.get_reports_by_month(user_id, year, month)
