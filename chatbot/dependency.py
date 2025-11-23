import psycopg2
from typing import Generator
from fastapi import Depends
from config import config

def get_db_conn() -> Generator:
    conn = psycopg2.connect(
        host=config.db_host,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password
    )
    try:
        yield conn
    finally:
        conn.close() # 요청 종료 시 자동 close
