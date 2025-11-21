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
