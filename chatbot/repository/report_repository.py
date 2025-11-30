# chatbot/repository/report_repository.py
import json
import logging
from datetime import date
from fastapi import Depends
from dependency import get_db_conn

logger = logging.getLogger()

class ReportRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_logs_by_period(self, user_id: str, start_date: date, end_date: date) -> list:
        sql = """
            SELECT user_input, bot_response, created_at
            FROM cbt_logs
            WHERE user_id = %s 
              AND created_at::date BETWEEN %s AND %s
            ORDER BY created_at ASC
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (user_id, start_date, end_date))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"기간별 로그 조회 실패: {e}")
            return []

    def save_weekly_report(self, user_id: str, start_date: date, end_date: date, report_data: dict) -> int:
        sql = """
            INSERT INTO weekly_reports (
                user_id, start_date, end_date, 
                report_title, report_content, emotions_summary
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING report_id;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    user_id, start_date, end_date,
                    report_data.get("title"),
                    report_data.get("content"),
                    json.dumps(report_data.get("emotions", {}), ensure_ascii=False)
                ))
                report_id = cur.fetchone()[0]
                self.conn.commit()
                return report_id
        except Exception as e:
            logger.error(f"주간 리포트 저장 실패: {e}")
            self.conn.rollback()
            return -1

    def find_reports_by_month(self, user_id: str, year: int, month: int) -> list:
        """
        특정 사용자의 특정 년/월(start_date 기준) 리포트를 조회합니다.
        """
        sql = """
            SELECT 
                report_id, 
                start_date, 
                end_date, 
                report_title, 
                report_content, 
                emotions_summary
            FROM weekly_reports
            WHERE user_id = %s
              AND EXTRACT(YEAR FROM start_date) = %s
              AND EXTRACT(MONTH FROM start_date) = %s
            ORDER BY start_date ASC
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (user_id, year, month))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"월별 리포트 조회 실패: {e}")
            return []

    def get_users_with_logs_in_period(self, start_date: date, end_date: date) -> list:
        """
        특정 기간에 cbt_logs에 데이터가 있는 모든 user_id 목록을 조회합니다.
        Returns:
            list: user_id 문자열 리스트
        """
        sql = """
            SELECT DISTINCT user_id
            FROM cbt_logs
            WHERE created_at::date BETWEEN %s AND %s
            ORDER BY user_id
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (start_date, end_date))
                rows = cur.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"기간별 사용자 목록 조회 실패: {e}")
            return []

    def check_report_exists(self, user_id: str, start_date: date, end_date: date) -> bool:
        """
        특정 사용자의 특정 기간에 이미 리포트가 존재하는지 확인합니다.
        Returns:
            bool: 리포트가 존재하면 True, 없으면 False
        """
        sql = """
            SELECT COUNT(*)
            FROM weekly_reports
            WHERE user_id = %s
              AND start_date = %s
              AND end_date = %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (user_id, start_date, end_date))
                count = cur.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"리포트 존재 여부 확인 실패: {e}")
            return False

# --- 의존성 주입용 헬퍼 함수 ---
def get_report_repository(conn=Depends(get_db_conn)) -> ReportRepository:
    return ReportRepository(conn)
