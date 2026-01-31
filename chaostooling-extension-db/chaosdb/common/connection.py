"""Common database connection utilities for chaosdb extension."""

import logging
import os
from typing import Optional

import mysql.connector
import psycopg2
from chaosdb.common.constants import ConnectionDefaults, DatabaseDefaults
from chaosdb.common.validation import (
    validate_database_name,
    validate_host,
    validate_port,
)
from mysql.connector import MySQLConnection
from psycopg2.extensions import connection

logger = logging.getLogger(__name__)


def get_postgres_connection_params(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> tuple[str, int, str, str, str]:
    """
    Get validated PostgreSQL connection parameters.

    Args:
        host: PostgreSQL host (defaults to POSTGRES_HOST env var or default)
        port: PostgreSQL port (defaults to POSTGRES_PORT env var or default)
        database: Database name (defaults to POSTGRES_DB env var or default)
        user: Database user (defaults to POSTGRES_USER env var or default)
        password: Database password (defaults to POSTGRES_PASSWORD env var or empty)

    Returns:
        Tuple of (host, port, database, user, password) with validated values
    """
    validated_host = validate_host(
        host or os.getenv("POSTGRES_HOST"),
        DatabaseDefaults.POSTGRES_DEFAULT_HOST,
        "host",
    )
    validated_port = validate_port(
        port or os.getenv("POSTGRES_PORT"),
        DatabaseDefaults.POSTGRES_PORT,
        "port",
    )
    validated_database = validate_database_name(
        database or os.getenv("POSTGRES_DB"),
        DatabaseDefaults.POSTGRES_DEFAULT_DB,
        "database",
    )
    validated_user = user or os.getenv(
        "POSTGRES_USER", DatabaseDefaults.POSTGRES_DEFAULT_USER
    )
    validated_password = password or os.getenv("POSTGRES_PASSWORD", "")

    return (
        validated_host,
        validated_port,
        validated_database,
        validated_user,
        validated_password,
    )


def create_postgres_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    connect_timeout: Optional[int] = None,
    autocommit: bool = False,
) -> connection:
    """
    Create a PostgreSQL connection with validated parameters.

    Args:
        host: PostgreSQL host (defaults to POSTGRES_HOST env var or default)
        port: PostgreSQL port (defaults to POSTGRES_PORT env var or default)
        database: Database name (defaults to POSTGRES_DB env var or default)
        user: Database user (defaults to POSTGRES_USER env var or default)
        password: Database password (defaults to POSTGRES_PASSWORD env var or empty)
        connect_timeout: Connection timeout in seconds (defaults to ConnectionDefaults.CONNECT_TIMEOUT)
        autocommit: Whether to enable autocommit mode (default: False)

    Returns:
        psycopg2 connection object

    Raises:
        psycopg2.Error: If connection fails
    """
    (
        validated_host,
        validated_port,
        validated_database,
        validated_user,
        validated_password,
    ) = get_postgres_connection_params(host, port, database, user, password)

    timeout = connect_timeout or ConnectionDefaults.CONNECT_TIMEOUT

    conn = psycopg2.connect(
        host=validated_host,
        port=validated_port,
        database=validated_database,
        user=validated_user,
        password=validated_password,
        connect_timeout=timeout,
    )

    if autocommit:
        conn.autocommit = True

    return conn


def get_mysql_connection_params(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> tuple[str, int, str, str, str]:
    """
    Get validated MySQL connection parameters.

    Args:
        host: MySQL host (defaults to MYSQL_HOST env var or default)
        port: MySQL port (defaults to MYSQL_PORT env var or default)
        database: Database name (defaults to MYSQL_DB env var or default)
        user: Database user (defaults to MYSQL_USER env var or default)
        password: Database password (defaults to MYSQL_PASSWORD env var or empty)

    Returns:
        Tuple of (host, port, database, user, password) with validated values
    """
    validated_host = validate_host(
        host or os.getenv("MYSQL_HOST"),
        DatabaseDefaults.MYSQL_DEFAULT_HOST,
        "host",
    )
    validated_port = validate_port(
        port or os.getenv("MYSQL_PORT"),
        DatabaseDefaults.MYSQL_PORT,
        "port",
    )
    validated_database = validate_database_name(
        database or os.getenv("MYSQL_DB"),
        DatabaseDefaults.MYSQL_DEFAULT_DB,
        "database",
    )
    validated_user = user or os.getenv(
        "MYSQL_USER", DatabaseDefaults.MYSQL_DEFAULT_USER
    )
    validated_password = password or os.getenv("MYSQL_PASSWORD", "")

    return (
        validated_host,
        validated_port,
        validated_database,
        validated_user,
        validated_password,
    )


def create_mysql_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    connection_timeout: Optional[int] = None,
) -> MySQLConnection:
    """
    Create a MySQL connection with validated parameters.

    Args:
        host: MySQL host (defaults to MYSQL_HOST env var or default)
        port: MySQL port (defaults to MYSQL_PORT env var or default)
        database: Database name (defaults to MYSQL_DB env var or default)
        user: Database user (defaults to MYSQL_USER env var or default)
        password: Database password (defaults to MYSQL_PASSWORD env var or empty)
        connection_timeout: Connection timeout in seconds (defaults to ConnectionDefaults.CONNECT_TIMEOUT)

    Returns:
        mysql.connector MySQLConnection object

    Raises:
        mysql.connector.Error: If connection fails
    """
    (
        validated_host,
        validated_port,
        validated_database,
        validated_user,
        validated_password,
    ) = get_mysql_connection_params(host, port, database, user, password)

    timeout = connection_timeout or ConnectionDefaults.CONNECT_TIMEOUT

    conn = mysql.connector.connect(
        host=validated_host,
        port=validated_port,
        database=validated_database,
        user=validated_user,
        password=validated_password,
        connection_timeout=timeout,
    )

    return conn
