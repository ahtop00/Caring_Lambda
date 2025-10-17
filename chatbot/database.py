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
        logger.info(f"DB에서 후보 정책 {len(results)}개를 찾았습니다.")
        return results
    except psycopg2.Error as e:
        logger.error(f"데이터베이스 오류 발생: {e}")
        raise
