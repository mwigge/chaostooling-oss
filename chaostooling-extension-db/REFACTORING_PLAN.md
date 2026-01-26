# Refactoring Plan - chaostooling-extension-db

## Overview

This extension provides chaos engineering actions and probes for multiple database and messaging systems. With 9 different systems (PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra, Kafka, RabbitMQ, ActiveMQ) and many similar operations, there's significant opportunity for code deduplication and standardization.

## Priority Levels

- **P0 (Critical)**: Must fix - blocking issues, security, correctness
- **P1 (High)**: Should fix - code quality, maintainability, consistency
- **P2 (Medium)**: Nice to have - improvements and optimizations
- **P3 (Low)**: Future enhancements

---

## P0: Critical Issues

### 1. Inconsistent Logging Libraries
**Files**: Multiple files in `actions/postgres/`
- Some files use `logzero` (e.g., `postgres_maintenance.py`, `postgres_cleanup.py`)
- Others use standard `logging`
- Should standardize on standard `logging` module

**Action**:
```python
# Remove: from logzero import logger
# Use: import logging; logger = logging.getLogger(__name__)
```

### 2. Generic Exception Handling
**Files**: Multiple files, especially `probes/postgres/postgres_system_metrics.py`
- `except Exception:` with `pass` hides errors
- Missing specific exception types
- Silent failures in probes

**Action**: Replace with specific exceptions and proper error handling

### 3. Missing Type Hints
**Files**: Many action and probe files
- Functions lack return type hints
- Parameters missing type hints
- Makes code harder to maintain and test

**Action**: Add comprehensive type hints throughout

---

## P1: Code Quality and Structure

### 4. Extract Common Database Connection Logic
**Files**: All database action files

**Issue**: Connection logic duplicated across PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra

**Action**: Create `chaosdb/common/connection.py`:
```python
class DatabaseConnectionFactory:
    @staticmethod
    def create_postgres_connection(host, port, database, user, password):
        # Common connection logic
    
    @staticmethod
    def create_mysql_connection(host, port, database, user, password):
        # Common connection logic
```

### 5. Extract Common Probe Patterns
**Files**: All probe files

**Issue**: Connectivity probes, status probes follow similar patterns

**Action**: Create base probe classes:
```python
class BaseConnectivityProbe:
    def probe_connectivity(self, host, port, **kwargs):
        # Common connectivity check logic

class BaseStatusProbe:
    def probe_status(self, **kwargs):
        # Common status check logic
```

### 6. Standardize Error Messages
**Files**: All action and probe files

**Issue**: Error messages inconsistent, some not informative

**Action**: Create error message constants and standardize format

### 7. Extract Magic Numbers and Strings
**Files**: All files

**Issue**: Hardcoded values like:
- Default ports (5432, 3306, 27017, etc.)
- Timeout values
- Default connection pool sizes
- Retry counts

**Action**: Create `chaosdb/common/constants.py`:
```python
class DatabaseDefaults:
    POSTGRES_PORT = 5432
    MYSQL_PORT = 3306
    MONGODB_PORT = 27017
    REDIS_PORT = 6379
    CASSANDRA_PORT = 9042
    DEFAULT_TIMEOUT = 30
    DEFAULT_POOL_SIZE = 10
```

### 8. Reduce Code Duplication in Similar Actions
**Files**: Actions with similar patterns (e.g., `*_connection_exhaustion.py`, `*_query_saturation.py`)

**Issue**: Similar logic repeated across databases

**Action**: Create base action classes or shared utilities:
```python
class BaseConnectionExhaustion:
    def exhaust_connections(self, connection_factory, max_connections):
        # Common connection exhaustion logic
```

### 9. Improve Configuration Management
**Files**: All files using `os.getenv()`

**Issue**: Environment variable access scattered, no validation

**Action**: Create configuration module:
```python
class DatabaseConfig:
    @staticmethod
    def get_postgres_config():
        # Centralized config with validation
```

### 10. Add Input Validation
**Files**: All action and probe functions

**Issue**: No validation of input parameters

**Action**: Add validation decorators or functions:
```python
def validate_connection_params(host, port, database):
    if not host:
        raise ValueError("host is required")
    if port < 1 or port > 65535:
        raise ValueError(f"Invalid port: {port}")
```

---

## P1: Testing

### 11. Add Unit Tests for Common Utilities
**Files**: Create `tests/test_common.py`

**Coverage**: Test common connection, probe, and utility functions

### 12. Add Integration Tests
**Files**: Create `tests/integration/`

**Coverage**: Test actual database connections (with test containers)

### 13. Add Test Fixtures
**Files**: Create `tests/fixtures/`

**Purpose**: Reusable test data and mock connections

### 14. Increase Test Coverage
**Files**: Currently only `test_postgres.py` exists

**Action**: Add tests for all database systems

---

## P1: Documentation

### 15. Add Comprehensive Docstrings
**Files**: All action and probe files

**Issue**: Some functions lack detailed docstrings

**Action**: Add docstrings with:
- Parameter descriptions
- Return value descriptions
- Example usage
- Raises sections

### 16. Create API Documentation
**Files**: Create `docs/API.md`

**Purpose**: Document all public APIs

### 17. Add Usage Examples
**Files**: Create `docs/examples/`

**Purpose**: Provide examples for each database system

---

## P2: Code Organization

### 18. Create Base Classes for Actions
**Files**: Create `chaosdb/actions/base.py`

**Purpose**: Common base classes for similar actions

### 19. Create Base Classes for Probes
**Files**: Create `chaosdb/probes/base.py`

**Purpose**: Common base classes for similar probes

### 20. Organize by Pattern Instead of System
**Files**: Consider restructuring

**Current**: `actions/postgres/`, `actions/mysql/`, etc.
**Alternative**: `actions/connection/`, `actions/query/`, etc. with system-specific implementations

**Note**: This is a larger refactoring, evaluate carefully

### 21. Extract Messaging Common Logic
**Files**: Kafka, RabbitMQ, ActiveMQ actions

**Issue**: Similar patterns for message flooding, queue saturation, etc.

**Action**: Create shared messaging utilities

### 22. Improve Import Organization
**Files**: All files

**Issue**: Imports not consistently organized

**Action**: Use isort and standardize import order

---

## P2: Performance and Optimization

### 23. Connection Pooling
**Files**: Database connection code

**Issue**: May create connections inefficiently

**Action**: Implement proper connection pooling where appropriate

### 24. Lazy Loading of Heavy Dependencies
**Files**: Files importing database drivers

**Issue**: All drivers loaded even if not used

**Action**: Lazy import database drivers

### 25. Optimize Probe Execution
**Files**: Probe files

**Issue**: Some probes may be inefficient

**Action**: Review and optimize probe queries

---

## P2: Feature Enhancements

### 26. Add Retry Logic
**Files**: Connection and action files

**Purpose**: Handle transient failures gracefully

### 27. Add Circuit Breaker Pattern
**Files**: Action files

**Purpose**: Prevent cascading failures

### 28. Add Health Check Utilities
**Files**: Create `chaosdb/common/health.py`

**Purpose**: Standardized health checks

### 29. Support Connection String Format
**Files**: Connection code

**Purpose**: Support URI-style connection strings in addition to individual parameters

---

## P3: Future Enhancements

### 30. Add Database-Specific Optimizations
**Files**: System-specific action files

**Purpose**: Leverage database-specific features

### 31. Add Metrics Collection
**Files**: All action files

**Purpose**: Collect and expose metrics about chaos operations

### 32. Add Distributed Tracing Integration
**Files**: All action files

**Purpose**: Better observability of chaos operations

**Note**: May already be partially implemented via chaosotel

### 33. Support Async Operations
**Files**: All action files

**Purpose**: Support async/await for better performance

---

## Implementation Phases

### Phase 1: Critical Fixes (P0)
1. Fix logging inconsistencies
2. Improve exception handling
3. Add basic type hints

**Estimated Time**: 4-6 hours

### Phase 2: Code Quality (P1 - High Priority)
4. Extract common connection logic
5. Extract common probe patterns
6. Standardize error messages
7. Extract magic numbers/strings
8. Add input validation

**Estimated Time**: 12-16 hours

### Phase 3: Testing (P1)
9. Add unit tests
10. Add integration tests
11. Increase coverage

**Estimated Time**: 16-20 hours

### Phase 4: Organization (P2)
12. Create base classes
13. Improve code organization
14. Extract messaging logic

**Estimated Time**: 12-16 hours

### Phase 5: Enhancements (P2-P3)
15. Add retry logic
16. Add circuit breakers
17. Performance optimizations

**Estimated Time**: 8-12 hours

---

## Code Review Checklist

- [ ] All P0 issues fixed
- [ ] Logging standardized
- [ ] Exception handling improved
- [ ] Type hints added
- [ ] Common code extracted
- [ ] Tests added with good coverage
- [ ] Documentation updated
- [ ] No code duplication
- [ ] Magic numbers/strings extracted
- [ ] Input validation added

---

## Notes

- This is a large codebase with many similar patterns
- Focus on extracting common patterns first
- Maintain backward compatibility
- Test thoroughly after refactoring
- Consider breaking changes in major version bump

