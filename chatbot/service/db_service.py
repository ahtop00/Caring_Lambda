# chatbot/service/db_service.py
import psycopg2
import json
import logging
from config import config

logger = logging.getLogger()

def get_db_connection():
    return psycopg2.connect(
        host=config.db_host,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password
    )

def search_welfare_services(embedding: list[float], locations: list[str] | None) -> list:
    sql_params = [json.dumps(embedding)]
    where_clauses = []

    if locations:
        loc_conditions = " OR ".join(["(province = %s OR city_district = %s)"] * len(locations))
        where_clauses.append(f"({loc_conditions})")
        for loc in locations:
            sql_params.extend([loc, loc])

    sql_where = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"""
        SELECT 
            (embedding <=> CAST(%s AS VECTOR(1024))) AS score,
            service_name, service_summary, detail_link, province, city_district
        FROM welfare_services {sql_where}
        ORDER BY score
        LIMIT 10;
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(sql_params))
                return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"복지 DB 오류: {e}")
        raise

def search_employment_jobs(embedding: list[float]) -> list:
    sql = """
        SELECT 
            (embedding <=> CAST(%s AS VECTOR(1024))) AS score,
            job_title, company_name, job_description, detail_link, location
        FROM employment_jobs
        ORDER BY score
        LIMIT 10;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (json.dumps(embedding),))
                return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"구인정보 DB 오류: {e}")
        raise

def get_chat_history(session_id: str, limit: int = 5) -> list:
    """
    특정 세션의 최근 대화 내역을 조회합니다.
    """
    sql = """
        SELECT user_input, bot_response 
        FROM cbt_logs 
        WHERE session_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()

        # 최신순으로 가져왔으니, 대화 흐름을 위해 과거순으로 뒤집어서 반환
        return rows[::-1] if rows else []
    except Exception as e:
        logger.error(f"대화 내역 조회 실패: {e}")
        return []

def log_cbt_session(user_id: str, session_id: str, user_input: str, bot_response: dict, embedding: list):
    """
    상담 로그와 임베딩 벡터를 DB에 저장합니다.
    """
    sql = """
        INSERT INTO cbt_logs (user_id, session_id, user_input, bot_response, embedding)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    user_id,
                    session_id,
                    user_input,
                    json.dumps(bot_response, ensure_ascii=False),
                    json.dumps(embedding)
                ))
                conn.commit()
    except Exception as e:
        logger.error(f"CBT 로그 저장 실패: {e}")
        # 로그 저장이 실패해도 사용자 응답은 나가야 하므로 에러를 띄우지 않고 로그만 남김
