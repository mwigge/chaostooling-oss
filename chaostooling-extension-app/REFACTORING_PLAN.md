# Refactoring Plan - chaostooling-extension-app

## Overview

This extension provides application-level chaos actions and probes. The codebase is small but has opportunities for improvement in code organization, type hints, and error handling.

## Priority Levels

- **P0 (Critical)**: Must fix
- **P1 (High)**: Should fix
- **P2 (Medium)**: Nice to have
- **P3 (Low)**: Future enhancements

---

## P0: Critical Issues

### 1. Add Type Hints
**Files**: `actions/client.py`, `actions/network.py`, `probes/observability.py`, `probes/validation.py`

**Issue**: Functions lack comprehensive type hints

**Action**: Add type hints for all parameters and return values

### 2. Improve Error Handling
**Files**: `actions/client.py`

**Issue**: Database and Kafka operations may fail without proper error handling

**Action**: Add specific exception types and better error messages

### 3. Add Input Validation
**Files**: All action and probe files

**Issue**: No validation of input parameters

**Action**: Add validation functions

---

## P1: Code Quality

### 4. Extract Magic Numbers and Strings
**Files**: `actions/client.py`

**Issue**: Hardcoded values like default ports, table names, etc.

**Action**: Move to constants:
```python
class AppDefaults:
    DEFAULT_POSTGRES_PORT = 5432
    DEFAULT_KAFKA_PORT = 9092
    PURCHASE_TABLE_NAME = "mobile_purchases"
```

### 5. Standardize Return Types
**Files**: All action and probe files

**Issue**: Inconsistent return value structures

**Action**: Standardize on `dict[str, Any]` with consistent keys

### 6. Extract Database Utilities
**Files**: `actions/client.py`

**Issue**: Database connection and table creation logic mixed with business logic

**Action**: Create `chaosapp/common/database.py`:
```python
class DatabaseUtils:
    @staticmethod
    def get_db_connection() -> psycopg2.connection:
        # Connection logic
    
    @staticmethod
    def ensure_table_exists(table_name: str, schema: str):
        # Table creation logic
```

### 7. Extract Kafka Utilities
**Files**: `actions/client.py`

**Issue**: Kafka publishing logic mixed with business logic

**Action**: Create `chaosapp/common/messaging.py`:
```python
class MessagingUtils:
    @staticmethod
    def publish_event(topic: str, event: dict, **kwargs):
        # Kafka publishing logic
```

### 8. Improve Code Organization
**Files**: `actions/client.py`

**Issue**: Large file with multiple responsibilities

**Action**: Consider splitting into:
- `actions/database.py` - Database operations
- `actions/messaging.py` - Messaging operations
- `actions/transactions.py` - Transaction logic

### 9. Add Logging Consistency
**Files**: All files

**Issue**: Logger names inconsistent

**Action**: Use `logger = logging.getLogger(__name__)`

---

## P1: Testing

### 10. Add Unit Tests
**Files**: Create `tests/test_actions.py`, `tests/test_probes.py`

**Coverage**: Test all actions and probes

### 11. Add Integration Tests
**Files**: Create `tests/integration/`

**Coverage**: Test actual database and messaging operations

### 12. Add Mock Fixtures
**Files**: Create `tests/fixtures/`

**Purpose**: Mock database connections and Kafka producers

---

## P1: Documentation

### 13. Improve Docstrings
**Files**: All files

**Issue**: Some functions lack detailed docstrings

**Action**: Add comprehensive docstrings with examples

### 14. Add Usage Examples
**Files**: Create `docs/examples/`

**Purpose**: Provide examples for application-level chaos

---

## P2: Code Organization

### 15. Create Common Utilities Module
**Files**: Create `chaosapp/common/`

**Purpose**: Shared utilities for database, messaging, etc.

### 16. Separate Concerns
**Files**: `actions/client.py`

**Issue**: Multiple concerns in one file

**Action**: Split into focused modules

### 17. Improve Import Organization
**Files**: All files

**Issue**: Imports not consistently organized

**Action**: Use isort and standardize

---

## P2: Features

### 18. Add Transaction Management
**Files**: `actions/client.py`

**Purpose**: Better transaction handling and rollback

### 19. Add Retry Logic
**Files**: `actions/client.py`

**Purpose**: Handle transient failures gracefully

### 20. Add Configuration Management
**Files**: Create `chaosapp/config.py`

**Purpose**: Centralized configuration

### 21. Add Health Checks
**Files**: `probes/observability.py`

**Purpose**: Enhanced health check probes

---

## P3: Future Enhancements

### 22. Support Multiple Databases
**Files**: `actions/client.py`

**Purpose**: Support MySQL, MongoDB, etc. in addition to PostgreSQL

### 23. Support Multiple Messaging Systems
**Files**: `actions/client.py`

**Purpose**: Support RabbitMQ, ActiveMQ, etc. in addition to Kafka

### 24. Add Observability Integration
**Files**: All files

**Purpose**: Better integration with chaosotel

### 25. Add Async Support
**Files**: All action files

**Purpose**: Support async/await for better performance

---

## Implementation Phases

### Phase 1: Critical Fixes (P0)
1. Add type hints
2. Improve error handling
3. Add input validation

**Estimated Time**: 2-3 hours

### Phase 2: Code Quality (P1)
4. Extract magic numbers
5. Extract utilities
6. Improve organization
7. Standardize return types

**Estimated Time**: 4-6 hours

### Phase 3: Testing (P1)
8. Add unit tests
9. Add integration tests

**Estimated Time**: 6-8 hours

### Phase 4: Organization (P2)
10. Create common module
11. Split large files

**Estimated Time**: 3-4 hours

---

## Code Review Checklist

- [ ] All P0 issues fixed
- [ ] Type hints added
- [ ] Error handling improved
- [ ] Input validation added
- [ ] Utilities extracted
- [ ] Tests added
- [ ] Documentation updated
- [ ] Code organized

---

## Notes

- This is a small codebase, refactoring should be straightforward
- Focus on separation of concerns
- Extract reusable utilities
- Consider this as a template for application-level chaos patterns

