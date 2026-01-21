import logging
import os
from typing import Optional

import psycopg2
from logzero import logger


def run_vacuum_analyze(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: Optional[str] = None,
) -> bool:
    """
    Run VACUUM ANALYZE on the database or a specific table.
    """
    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "postgres")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5,
        )
        # VACUUM cannot run inside a transaction block
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        if table_name:
            logger.info(f"Running VACUUM ANALYZE on {table_name}")
            cursor.execute(f"VACUUM ANALYZE {table_name};")
        else:
            logger.info("Running VACUUM ANALYZE on database")
            cursor.execute("VACUUM ANALYZE;")

        cursor.close()
        conn.close()

        logger.info("VACUUM ANALYZE completed")
        return True
    except Exception as e:
        logger.error(f"Failed to run VACUUM ANALYZE: {e}")
        return False
