import logging
import os
from typing import Optional

import psycopg2
from chaosdb.common.constants import ConnectionDefaults, DatabaseDefaults
from chaosdb.common.validation import (
    validate_database_name,
    validate_host,
    validate_port,
)

logger = logging.getLogger(__name__)


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
    host = validate_host(
        host or os.getenv("POSTGRES_HOST"),
        DatabaseDefaults.POSTGRES_DEFAULT_HOST,
        "host",
    )
    port = validate_port(
        port or os.getenv("POSTGRES_PORT"),
        DatabaseDefaults.POSTGRES_PORT,
        "port",
    )
    database = validate_database_name(
        database or os.getenv("POSTGRES_DB"),
        DatabaseDefaults.POSTGRES_DEFAULT_DB,
        "database",
    )
    user = user or os.getenv("POSTGRES_USER", DatabaseDefaults.POSTGRES_DEFAULT_USER)
    password = password or os.getenv("POSTGRES_PASSWORD", "")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=ConnectionDefaults.CONNECT_TIMEOUT,
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
    except psycopg2.OperationalError as e:
        logger.error(f"PostgreSQL connection error while running VACUUM ANALYZE: {e}")
        return False
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL database error while running VACUUM ANALYZE: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error running VACUUM ANALYZE: {e}", exc_info=True)
        return False
