import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "testdb"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def ensure_table_exists():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mobile_edge_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name VARCHAR(255) NOT NULL,
                    value FLOAT NOT NULL,
                    tags JSONB
                );
            """)
        conn.commit()
    finally:
        conn.close()

def log_metric(metric_name: str, value: float, tags: Dict[str, Any] = None) -> bool:
    """
    Log a metric to the PostgreSQL database.
    """
    if tags is None:
        tags = {}
    
    ensure_table_exists()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mobile_edge_metrics (metric_name, value, tags) VALUES (%s, %s, %s)",
                (metric_name, value, json.dumps(tags))
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to log metric: {e}")
        return False
    finally:
        conn.close()

def get_metrics(metric_name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Retrieve recent metrics from the database.
    """
    ensure_table_exists()
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM mobile_edge_metrics WHERE metric_name = %s ORDER BY timestamp DESC LIMIT %s",
                (metric_name, limit)
            )
            return cursor.fetchall()
    finally:
        conn.close()
