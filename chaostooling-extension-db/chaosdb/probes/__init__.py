"""Chaos Toolkit Database Extension - Probes Package."""

# Import all probe modules to make them discoverable
# Make imports optional to handle missing system dependencies
try:
    from . import activemq
except ImportError:
    pass

try:
    from . import cassandra
except ImportError:
    pass

try:
    from . import kafka
except ImportError:
    pass

try:
    from . import mongodb
except ImportError:
    pass

try:
    from . import mssql
except ImportError:
    pass

try:
    from . import mysql
except ImportError:
    pass

try:
    from . import postgres
except ImportError:
    pass

try:
    from . import rabbitmq
except ImportError:
    pass

try:
    from . import redis
except ImportError:
    pass

__all__ = [
    "activemq",
    "cassandra",
    "kafka",
    "mongodb",
    "mssql",
    "mysql",
    "postgres",
    "rabbitmq",
    "redis",
]
