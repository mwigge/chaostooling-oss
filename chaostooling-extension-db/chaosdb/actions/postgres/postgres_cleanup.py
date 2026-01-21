import logging
import os
from typing import Optional

import psycopg2
from logzero import logger


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
    except Exception as e:
        logger.error(f"Failed to terminate slow transactions: {e}")
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
    except Exception as e:
        logger.error(f"Failed to terminate idle connections: {e}")
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
    except Exception as e:
        logger.error(f"Failed to release blocking locks: {e}")
        return False
