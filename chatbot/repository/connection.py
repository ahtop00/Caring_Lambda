# chatbot/repository/connection.py
import psycopg2
from config import config

def get_db_connection():
    return psycopg2.connect(
        host=config.db_host,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password
    )
