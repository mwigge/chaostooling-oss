import logging
import os
from typing import Optional

import psycopg2
from chaosdb.common.connection import create_postgres_connection
from chaosdb.common.constants import DatabaseDefaults
from chaosdb.common.validation import (
    validate_database_name,
    validate_host,
    validate_port,
)

logger = logging.getLogger(__name__)


def terminate_slow_transactions(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    max_duration_seconds: int = 60,
) -> bool:
    """
    Terminate transactions running longer than max_duration_seconds.
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
        conn = create_postgres_connection(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE state = 'active'
              AND xact_start < NOW() - INTERVAL '%s seconds'
              AND pid <> pg_backend_pid();
            """,
            (max_duration_seconds,),
        )
        terminated_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Terminated {terminated_count} slow transactions")
        return True
    except psycopg2.OperationalError as e:
        logger.error(
            f"PostgreSQL connection error while terminating slow transactions: {e}"
        )
        return False
    except psycopg2.Error as e:
        logger.error(
            f"PostgreSQL database error while terminating slow transactions: {e}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error terminating slow transactions: {e}", exc_info=True
        )
        return False


def terminate_idle_connections(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    max_idle_seconds: int = 300,
) -> bool:
    """
    Terminate connections idle for longer than max_idle_seconds.
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
        conn = create_postgres_connection(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE state = 'idle'
              AND state_change < NOW() - INTERVAL '%s seconds'
              AND pid <> pg_backend_pid();
            """,
            (max_idle_seconds,),
        )
        terminated_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Terminated {terminated_count} idle connections")
        return True
    except psycopg2.OperationalError as e:
        logger.error(
            f"PostgreSQL connection error while terminating idle connections: {e}"
        )
        return False
    except psycopg2.Error as e:
        logger.error(
            f"PostgreSQL database error while terminating idle connections: {e}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error terminating idle connections: {e}", exc_info=True
        )
        return False


def release_blocking_locks(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """
    Terminate sessions that are blocking other sessions.
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
        conn = create_postgres_connection(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        cursor = conn.cursor()

        # Identify blocking pids
        cursor.execute(
            """
            SELECT DISTINCT pg_blocking_pids(pid)
            FROM pg_stat_activity
            WHERE cardinality(pg_blocking_pids(pid)) > 0;
            """
        )
        rows = cursor.fetchall()
        blocking_pids = set()
        for row in rows:
            for pid in row[0]:
                blocking_pids.add(pid)

        terminated_count = 0
        for pid in blocking_pids:
            cursor.execute("SELECT pg_terminate_backend(%s)", (pid,))
            terminated_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Terminated {terminated_count} blocking sessions")
        return True
    except psycopg2.OperationalError as e:
        logger.error(f"PostgreSQL connection error while releasing blocking locks: {e}")
        return False
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL database error while releasing blocking locks: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error releasing blocking locks: {e}", exc_info=True)
        return False
