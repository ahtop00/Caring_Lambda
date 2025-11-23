# chatbot/repository/search_repository.py
import json
import logging
from fastapi import Depends
from dependency import get_db_conn

logger = logging.getLogger()

class SearchRepository:
    def __init__(self, conn):
        self.conn = conn

    def search_welfare_services(self, embedding: list[float], locations: list[str] | None) -> list:
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
            with self.conn.cursor() as cur:
                cur.execute(sql, tuple(sql_params))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"복지 DB 오류: {e}")
            raise

    def search_employment_jobs(self, embedding: list[float]) -> list:
        sql = """
            SELECT 
                (embedding <=> CAST(%s AS VECTOR(1024))) AS score,
                job_title, company_name, job_description, detail_link, location
            FROM employment_jobs
            ORDER BY score
            LIMIT 10;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (json.dumps(embedding),))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"구인정보 DB 오류: {e}")
            raise

# --- 의존성 주입용 헬퍼 함수 ---
def get_search_repository(conn=Depends(get_db_conn)) -> SearchRepository:
    return SearchRepository(conn)
