# database.py
import psycopg2
import json
import logging
from config import config

logger = logging.getLogger()

def search_welfare_services(embedding: list[float], locations: list[str] | None) -> list:
    """임베딩과 지역명으로 복지 서비스를 검색하고 score를 반환합니다."""
    sql_params = []
    where_clauses = []
    if locations:
        loc_conditions = " OR ".join(["(province = %s OR city_district = %s)"] * len(locations))
        where_clauses.append(f"({loc_conditions})")
        for loc in locations:
            sql_params.extend([loc, loc])

    sql_where = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql_params.append(json.dumps(embedding))

    # [수정] (embedding <=> ...) AS score 추가
    sql = f"""
        SELECT 
            (embedding <=> CAST(%s AS VECTOR(1024))) AS score,
            service_name, service_summary, detail_link, province, city_district
        FROM welfare_services {sql_where}
        ORDER BY score
        LIMIT 10;
    """

    results = []
    try:
        with psycopg2.connect(
                host=config.db_host,
                database=config.db_name,
                user=config.db_user,
                password=config.db_password
        ) as conn:
            with conn.cursor() as cur:
                # [수정] embedding이 %s에 두 번 바인딩됨
                cur.execute(sql, (sql_params[-1], *sql_params))
                results = cur.fetchall()
        return results
    except psycopg2.Error as e:
        logger.error(f"복지 DB 오류 발생: {e}")
        raise

def search_employment_jobs(embedding: list[float]) -> list:
    """임베딩으로 구인 정보를 검색하고 score를 반환합니다."""

    # [수정] (embedding <=> ...) AS score 추가 및 컬럼 순서 변경
    sql = """
        SELECT 
            (embedding <=> CAST(%s AS VECTOR(1024))) AS score,
            job_title, 
            company_name, 
            job_description, 
            detail_link, 
            location
        FROM employment_jobs
        ORDER BY score
        LIMIT 10;
    """
    results = []
    try:
        with psycopg2.connect(
                host=config.db_host,
                database=config.db_name,
                user=config.db_user,
                password=config.db_password
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (json.dumps(embedding),))
                results = cur.fetchall()
        return results
    except psycopg2.Error as e:
        logger.error(f"구인정보 DB 오류 발생: {e}")
        raise
