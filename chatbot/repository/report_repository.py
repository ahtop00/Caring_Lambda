# chatbot/repository/report_repository.py
import json
import logging
from datetime import date
from repository.connection import get_db_connection

logger = logging.getLogger()

def get_logs_by_period(user_id: str, start_date: date, end_date: date) -> list:
    """지정된 기간 내의 대화 로그 조회"""
    sql = """
        SELECT user_input, bot_response, created_at
        FROM cbt_logs
        WHERE user_id = %s 
          AND created_at::date BETWEEN %s AND %s
        ORDER BY created_at ASC
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, start_date, end_date))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"기간별 로그 조회 실패: {e}")
        return []

def save_weekly_report(user_id: str, start_date: date, end_date: date, report_data: dict) -> int:
    """생성된 주간 리포트 DB 저장"""
    sql = """
        INSERT INTO weekly_reports (
            user_id, start_date, end_date, 
            report_title, report_content, emotions_summary
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING report_id;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    user_id, start_date, end_date,
                    report_data.get("title"),
                    report_data.get("content"),
                    json.dumps(report_data.get("emotions", {}), ensure_ascii=False)
                ))
                report_id = cur.fetchone()[0]
                conn.commit()
                return report_id
    except Exception as e:
        logger.error(f"주간 리포트 저장 실패: {e}")
        return -1
