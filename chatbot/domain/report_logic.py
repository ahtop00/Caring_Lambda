# chatbot/domain/report_logic.py
import logging
import json
import time
from datetime import timedelta, date
from fastapi import Depends

from exception import AppError
from service.llm_service import LLMService, get_llm_service
from repository.report_repository import ReportRepository, get_report_repository
from prompts.report import get_report_prompt
from schema.history import WeeklyReportResponse, WeeklyReportItem, MonthlyReportListResponse
from util.json_parser import parse_llm_json

logger = logging.getLogger()

class ReportService:
    def __init__(self, report_repo: ReportRepository, llm_service: LLMService):
        self.report_repo = report_repo
        self.llm_service = llm_service

    def generate_weekly_report(self, user_id: str, target_date: date) -> WeeklyReportResponse:
        try:
            # 날짜 계산
            start_of_week = target_date - timedelta(days=target_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            period_str = f"{start_of_week.strftime('%Y-%m-%d')} ~ {end_of_week.strftime('%Y-%m-%d')}"

            # DB 조회
            logs = self.report_repo.get_logs_by_period(user_id, start_of_week, end_of_week)

            if not logs:
                raise AppError(
                    status_code=404,
                    message="해당 기간에 대화 기록이 없어 리포트를 생성할 수 없습니다."
                )

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
                report_data = parse_llm_json(llm_raw)
            except ValueError as parse_e:
                # 어떤 내용이라도 저장하거나, 명확하게 에러 로그를 남기는 것이 좋음
                logger.error(f"리포트 생성 중 파싱 오류: {parse_e}")
                report_data = {
                    "title": "주간 마음 정리 (생성 실패)",
                    "content": llm_raw, # 원본 텍스트라도 저장 시도
                    "emotions": {}
                }

            # DB 저장
            report_id = self.report_repo.save_weekly_report(user_id, start_of_week, end_of_week, report_data)

            if report_id == -1:
                raise Exception("DB 저장 실패")

            return WeeklyReportResponse(
                report_id=report_id,
                title=report_data.get("title", "무제"),
                content=report_data.get("content", ""),
                period=period_str,
                emotions=report_data.get("emotions", {})
            )

        except AppError as ae:
            raise ae
        except Exception as e:
            logger.error(f"주간 리포트 생성 중 시스템 오류: {e}", exc_info=True)
            raise AppError(
                status_code=500,
                message="리포트 생성 중 알 수 없는 오류가 발생했습니다.",
                detail=str(e)
            )

    def get_reports_by_month(self, user_id: str, year: int, month: int) -> MonthlyReportListResponse:
        try:
            rows = self.report_repo.find_reports_by_month(user_id, year, month)

            if not rows:
                raise AppError(
                    status_code=404,
                    message=f"{year}년 {month}월에 생성된 마음 소설이 없습니다.",
                    detail=f"No reports found for user={user_id}, period={year}-{month}"
                )

            reports = []
            for r in rows:
                # r: (report_id, start_date, end_date, report_title, report_content, emotions_summary)
                emotions = r[5]
                if isinstance(emotions, str):
                    try:
                        emotions = json.loads(emotions)
                    except:
                        emotions = {}

                period_str = f"{r[1].strftime('%Y-%m-%d')} ~ {r[2].strftime('%Y-%m-%d')}"

                reports.append(WeeklyReportItem(
                    report_id=r[0],
                    title=r[3] or "제목 없음",
                    content=r[4] or "",
                    period=period_str,
                    emotions=emotions or {},
                    created_at=r[1]
                ))

            return MonthlyReportListResponse(
                year=year,
                month=month,
                reports=reports
            )

        except AppError as ae:
            raise ae

        except Exception as e:
            logger.error(f"월별 리포트 조회 중 시스템 오류: {e}", exc_info=True)
            raise AppError(
                status_code=500,
                message="리포트 목록을 불러오는 중 알 수 없는 오류가 발생했습니다.",
                detail=str(e)
            )

    def generate_weekly_reports_for_period(self, target_date: date, start_time=None, max_execution_time=870) -> dict:
        """
        전주(지난 주)에 해당하는 기간에 cbt_logs에 데이터가 있는 모든 사용자에 대해 주간 리포트를 생성합니다.
        AWS 스케줄러에서 호출하는 배치 처리 메서드입니다.
        (월요일에 실행되면 그 전주 리포트를 생성)
        
        Args:
            target_date: 현재 날짜 (전주의 시작일~종료일 계산에 사용)
            start_time: 작업 시작 시간 (time.time(), 타임아웃 체크용)
            max_execution_time: 최대 실행 시간(초), 기본값 870초 (14분 30초)
        
        Returns:
            dict: {
                "success_count": int,
                "failed_count": int,
                "skipped_count": int,
                "total_users": int,
                "processed_users": int,  # 실제 처리된 사용자 수
                "remaining_users": int,  # 미처리 사용자 수 (타임아웃 시)
                "period": str,
                "is_timeout": bool,  # 타임아웃으로 인한 중단 여부
                "results": List[dict]  # 각 사용자별 생성 결과
            }
        """
        try:
            # 전주(지난 주) 기간 계산
            # 1. 현재 주의 시작일 계산
            current_week_start = target_date - timedelta(days=target_date.weekday())
            # 2. 전주의 시작일 = 현재 주 시작일 - 7일
            start_of_prev_week = current_week_start - timedelta(days=7)
            # 3. 전주의 종료일 = 전주 시작일 + 6일
            end_of_prev_week = start_of_prev_week + timedelta(days=6)
            period_str = f"{start_of_prev_week.strftime('%Y-%m-%d')} ~ {end_of_prev_week.strftime('%Y-%m-%d')}"
            
            logger.info(f"배치 주간 리포트 생성 시작 (전주): period={period_str}")
            
            # 해당 기간에 로그가 있는 모든 사용자 조회
            user_ids = self.report_repo.get_users_with_logs_in_period(start_of_prev_week, end_of_prev_week)
            
            if not user_ids:
                logger.info(f"기간 {period_str}에 로그가 있는 사용자가 없습니다.")
                return {
                    "success_count": 0,
                    "failed_count": 0,
                    "total_users": 0,
                    "period": period_str,
                    "results": []
                }
            
            # 중복 제거 (혹시 모를 중복 방지)
            unique_user_ids = list(set(user_ids))
            logger.info(f"리포트 생성 대상 사용자 수: {len(unique_user_ids)} (중복 제거 후)")
            
            success_count = 0
            failed_count = 0
            skipped_count = 0
            results = []
            
            # 전주의 임의 날짜 (리포트 생성에 사용)
            prev_week_date = start_of_prev_week + timedelta(days=3)  # 전주 수요일
            
            # 타임아웃 체크를 위한 안전 마진 (30초)
            TIMEOUT_BUFFER_SECONDS = 30
            
            # 각 사용자별로 리포트 생성
            for idx, user_id in enumerate(unique_user_ids, 1):
                # 타임아웃 체크 (start_time이 제공된 경우)
                if start_time:
                    elapsed_time = time.time() - start_time
                    remaining_time = max_execution_time - elapsed_time
                    
                    if remaining_time < TIMEOUT_BUFFER_SECONDS:
                        logger.warning(
                            f"타임아웃 임박 (경과: {elapsed_time:.1f}초, 남은 시간: {remaining_time:.1f}초). "
                            f"처리 중단 - 완료: {idx-1}/{len(unique_user_ids)}"
                        )
                        # 현재까지의 결과 반환
                        return {
                            "success_count": success_count,
                            "failed_count": failed_count,
                            "skipped_count": skipped_count,
                            "total_users": len(unique_user_ids),
                            "processed_users": idx - 1,
                            "remaining_users": len(unique_user_ids) - (idx - 1),
                            "period": period_str,
                            "is_timeout": True,
                            "results": results
                        }
                
                try:
                    # 이미 리포트가 존재하는지 확인
                    if self.report_repo.check_report_exists(user_id, start_of_prev_week, end_of_prev_week):
                        logger.info(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id}: 이미 리포트가 존재하여 스킵")
                        skipped_count += 1
                        results.append({
                            "user_id": user_id,
                            "status": "skipped",
                            "reason": "already_exists"
                        })
                        # 스킵한 경우에도 3초 대기 (일관성 유지)
                        if idx < len(unique_user_ids):
                            time.sleep(3)
                        continue
                    
                    logger.info(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id} 리포트 생성 시작")
                    
                    # 기존 generate_weekly_report 메서드 재사용 (전주 날짜 전달)
                    report = self.generate_weekly_report(user_id, prev_week_date)
                    success_count += 1
                    results.append({
                        "user_id": user_id,
                        "status": "success",
                        "report_id": report.report_id
                    })
                    logger.info(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id} 리포트 생성 성공: report_id={report.report_id}, period={period_str}")
                    
                    # LLM 호출 간 3초 대기 (마지막 사용자는 대기 불필요)
                    if idx < len(unique_user_ids):
                        logger.debug(f"다음 사용자 처리 전 3초 대기 중...")
                        time.sleep(3)
                        
                except AppError as ae:
                    # 404 (로그 없음)는 정상적인 경우이므로 실패로 카운트하지 않음
                    if ae.status_code == 404:
                        logger.info(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id}: 해당 기간에 로그가 없어 리포트 생성 스킵")
                        skipped_count += 1
                        results.append({
                            "user_id": user_id,
                            "status": "skipped",
                            "reason": "no_logs"
                        })
                    else:
                        failed_count += 1
                        results.append({
                            "user_id": user_id,
                            "status": "failed",
                            "error": ae.message
                        })
                        logger.error(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id} 리포트 생성 실패: {ae.message}")
                    
                    # 실패/스킵한 경우에도 3초 대기
                    if idx < len(unique_user_ids):
                        time.sleep(3)
                        
                except Exception as e:
                    failed_count += 1
                    results.append({
                        "user_id": user_id,
                        "status": "failed",
                        "error": str(e)
                    })
                    logger.error(f"[{idx}/{len(unique_user_ids)}] 사용자 {user_id} 리포트 생성 중 예외 발생: {e}", exc_info=True)
                    
                    # 예외 발생한 경우에도 3초 대기
                    if idx < len(unique_user_ids):
                        time.sleep(3)
            
            logger.info(f"배치 주간 리포트 생성 완료: 성공={success_count}, 실패={failed_count}, 스킵={skipped_count}, 총={len(unique_user_ids)}")
            
            return {
                "success_count": success_count,
                "failed_count": failed_count,
                "skipped_count": skipped_count,
                "total_users": len(unique_user_ids),
                "processed_users": len(unique_user_ids),
                "remaining_users": 0,
                "period": period_str,
                "is_timeout": False,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"배치 리포트 생성 중 시스템 오류: {e}", exc_info=True)
            raise AppError(
                status_code=500,
                message="배치 리포트 생성 중 알 수 없는 오류가 발생했습니다.",
                detail=str(e)
            )

# --- 의존성 주입용 함수 ---
def get_report_service(
        report_repo: ReportRepository = Depends(get_report_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> ReportService:
    return ReportService(report_repo, llm_service)
