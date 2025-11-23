# chatbot/domain/report_logic.py
import json
import re
import logging
from datetime import timedelta, date
from fastapi import HTTPException, Depends

from service.llm_service import LLMService, get_llm_service
from repository.report_repository import ReportRepository, get_report_repository
from prompts.report import get_report_prompt
from schema.history import WeeklyReportResponse

logger = logging.getLogger()

class ReportService:
    def __init__(self, report_repo: ReportRepository, llm_service: LLMService):
        self.report_repo = report_repo
        self.llm_service = llm_service

    def generate_weekly_report(self, user_id: str, target_date: date) -> WeeklyReportResponse:
        # 날짜 계산
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        period_str = f"{start_of_week.strftime('%Y-%m-%d')} ~ {end_of_week.strftime('%Y-%m-%d')}"

        # DB 조회
        logs = self.report_repo.get_logs_by_period(user_id, start_of_week, end_of_week)

        if not logs:
            raise HTTPException(status_code=404, detail="해당 기간에 대화 기록이 없어 리포트를 생성할 수 없습니다.")

        # 프롬프트 구성
        logs_text = ""
        for log in logs:
            day_str = log[2].strftime("%A")
            bot_res = log[1] if isinstance(log[1], dict) else {}
            empathy = bot_res.get('empathy', '')

            logs_text += f"[{day_str}] 나: {log[0]}\n상담사: {empathy}\n---\n"

        # LLM 호출
        prompt = get_report_prompt(logs_text, period_str)
        llm_raw = self.llm_service.get_llm_response(prompt)

        # JSON 파싱
        try:
            json_match = re.search(r'\{.*\}', llm_raw, re.DOTALL)
            if json_match:
                report_data = json.loads(json_match.group(0))
            else:
                raise ValueError("JSON 형식 아님")
        except Exception as e:
            logger.error(f"리포트 생성 중 파싱 오류: {e}")
            report_data = {
                "title": "주간 마음 정리",
                "content": llm_raw,
                "emotions": {}
            }

        # DB 저장
        report_id = self.report_repo.save_weekly_report(user_id, start_of_week, end_of_week, report_data)

        return WeeklyReportResponse(
            report_id=report_id,
            title=report_data.get("title", "무제"),
            content=report_data.get("content", ""),
            period=period_str,
            emotions=report_data.get("emotions", {})
        )

# --- 의존성 주입용 함수 ---
def get_report_service(
        report_repo: ReportRepository = Depends(get_report_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> ReportService:
    return ReportService(report_repo, llm_service)
