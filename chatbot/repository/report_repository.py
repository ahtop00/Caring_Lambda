# chatbot/repository/report_repository.py
from repository.connection import get_db_connection
from datetime import date

def get_logs_by_period(user_id: str, start_date: date, end_date: date) -> list:
    sql = """
        SELECT user_input, bot_response, created_at
        FROM cbt_logs
        WHERE user_id = %s AND created_at::date BETWEEN %s AND %s
        ORDER BY created_at ASC
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, start_date, end_date))
            return cur.fetchall()

# save_weekly_report 함수도 여기에 추가하면 됩니다.
