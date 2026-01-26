"""
Common constants for database and messaging system defaults.

This module provides centralized constants for default ports, timeouts,
and other configuration values used across the chaosdb extension.
"""


class DatabaseDefaults:
    """Default values for database connections."""

    # PostgreSQL
    POSTGRES_PORT = 5432
    POSTGRES_DEFAULT_DB = "postgres"
    POSTGRES_DEFAULT_USER = "postgres"
    POSTGRES_DEFAULT_HOST = "localhost"

    # MySQL
    MYSQL_PORT = 3306
    MYSQL_DEFAULT_DB = "mysql"
    MYSQL_DEFAULT_USER = "root"
    MYSQL_DEFAULT_HOST = "localhost"

    # MSSQL
    MSSQL_PORT = 1433
    MSSQL_DEFAULT_DB = "master"
    MSSQL_DEFAULT_USER = "sa"
    MSSQL_DEFAULT_HOST = "localhost"

    # MongoDB
    MONGODB_PORT = 27017
    MONGODB_DEFAULT_DB = "admin"
    MONGODB_DEFAULT_USER = "admin"
    MONGODB_DEFAULT_HOST = "localhost"

    # Redis
    REDIS_PORT = 6379
    REDIS_DEFAULT_HOST = "localhost"
    REDIS_DEFAULT_DB = 0

    # Cassandra
    CASSANDRA_PORT = 9042
    CASSANDRA_DEFAULT_HOST = "localhost"
    CASSANDRA_DEFAULT_KEYSPACE = "system"


class MessagingDefaults:
    """Default values for messaging systems."""

    # Kafka
    KAFKA_PORT = 9092
    KAFKA_DEFAULT_HOST = "localhost"
    KAFKA_DEFAULT_TOPIC = "test"

    # RabbitMQ
    RABBITMQ_PORT = 5672
    RABBITMQ_DEFAULT_HOST = "localhost"
    RABBITMQ_DEFAULT_VHOST = "/"
    RABBITMQ_DEFAULT_USER = "guest"
    RABBITMQ_DEFAULT_QUEUE = "test"

    # ActiveMQ
    ACTIVEMQ_PORT = 61616
    ACTIVEMQ_DEFAULT_HOST = "localhost"
    ACTIVEMQ_DEFAULT_QUEUE = "test"


class ConnectionDefaults:
    """Default values for connection settings."""

    CONNECT_TIMEOUT = 5
    DEFAULT_TIMEOUT = 30
    DEFAULT_POOL_SIZE = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1
    THREAD_JOIN_TIMEOUT_SHORT = 5  # Short timeout for thread joins
    THREAD_JOIN_TIMEOUT_LONG = 10  # Longer timeout for thread joins


class StressDefaults:
    """Default values for stress testing."""

    DEFAULT_DURATION_SECONDS = 60
    DEFAULT_NUM_THREADS = 10
    DEFAULT_NUM_CONNECTIONS = 100
    DEFAULT_QUERY_COUNT = 1000
