# database.py
import psycopg2
import json
import logging
from config import config

logger = logging.getLogger()

def search_welfare_services(embedding: list[float], locations: list[str] | None) -> list:
    """임베딩과 지역명으로 복지 서비스를 검색합니다."""
    sql_params = []
    where_clauses = []
    if locations:
        loc_conditions = " OR ".join(["(province = %s OR city_district = %s)"] * len(locations))
        where_clauses.append(f"({loc_conditions})")
        for loc in locations:
            sql_params.extend([loc, loc])

    sql_where = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql_params.append(json.dumps(embedding))

    # 기존 쿼리 유지
    sql = f"""
        SELECT service_name, service_summary, detail_link, province, city_district
        FROM welfare_services {sql_where}
        ORDER BY embedding <=> CAST(%s AS VECTOR(1024))
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
                cur.execute(sql, tuple(sql_params))
                results = cur.fetchall()
        logger.info(f"DB(welfare)에서 후보 정책 {len(results)}개를 찾았습니다.")
        return results
    except psycopg2.Error as e:
        logger.error(f"복지 DB 오류 발생: {e}")
        raise

def search_employment_jobs(embedding: list[float]) -> list:
    """임베딩으로 구인 정보를 검색합니다."""

    # data_processor.normalize_results가 처리할 수 있도록 원본 컬럼 반환
    sql = """
        SELECT 
            job_title, 
            company_name, 
            job_description, 
            detail_link, 
            location
        FROM employment_jobs
        ORDER BY embedding <=> CAST(%s AS VECTOR(1024))
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
                # 임베딩 값만 파라미터로 전달
                cur.execute(sql, (json.dumps(embedding),))
                results = cur.fetchall()
        logger.info(f"DB(employment)에서 후보 구인정보 {len(results)}개를 찾았습니다.")
        return results
    except psycopg2.Error as e:
        logger.error(f"구인정보 DB 오류 발생: {e}")
        raise

def search_services(intent: str, embedding: list[float], locations: list[str] | None) -> (list, str):
    """
    사용자 의도(intent)에 따라 적절한 DB 테이블을 검색합니다.
    (검색 결과, 검색 타입) 튜플을 반환합니다.
    """
    if intent == "EMPLOYMENT":
        results = search_employment_jobs(embedding)
        return results, "EMPLOYMENT"
    else:
        # 기본값은 '복지' 검색
        results = search_welfare_services(embedding, locations)
        return results, "WELFARE"
