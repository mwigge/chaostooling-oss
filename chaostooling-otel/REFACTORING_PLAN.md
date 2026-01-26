# Refactoring Plan - chaostooling-otel

## Overview

This is the core observability library providing OpenTelemetry integration for chaos engineering. It's well-structured but has opportunities for improvement in error handling, type hints, and code organization.

## Priority Levels

- **P0 (Critical)**: Must fix
- **P1 (High)**: Should fix
- **P2 (Medium)**: Nice to have
- **P3 (Low)**: Future enhancements

---

## P0: Critical Issues

### 1. Improve Exception Handling in Core Classes
**Files**: `core/metrics_core.py`, `core/log_core.py`, `core/trace_core.py`, `core/compliance_core.py`

**Issue**: Generic `except Exception` catches too broadly, may hide important errors

**Action**: Use specific exception types:
```python
# Instead of:
except Exception as e:
    logger.error(f"Error: {e}")

# Use:
except (ValueError, AttributeError) as e:
    logger.error(f"Invalid parameter: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise RuntimeError(f"Failed to record metric: {e}") from e
```

### 2. Add Type Hints Throughout
**Files**: All files, especially `otel.py`, `decorators.py`

**Issue**: Some functions lack comprehensive type hints

**Action**: Add type hints for all parameters and return values

### 3. Validate Initialization State
**Files**: `otel.py`, `control.py`

**Issue**: Functions may be called before initialization

**Action**: Add proper checks and clear error messages

---

## P1: Code Quality

### 4. Extract Magic Numbers and Strings
**Files**: All core files

**Issue**: Hardcoded values like metric names, attribute keys, etc.

**Action**: Create constants:
```python
class MetricNames:
    OPERATION_DURATION = "chaos_operation_duration_milliseconds"
    OPERATION_COUNT = "chaos_operation_success_total"
    # ...

class AttributeKeys:
    OPERATION_NAME = "operation_name"
    OPERATION_STATUS = "operation_status"
    # ...
```

### 5. Standardize Error Messages
**Files**: All files

**Issue**: Error messages inconsistent

**Action**: Create error message constants or standardize format

### 6. Improve Logging Consistency
**Files**: All files

**Issue**: Logger names and levels inconsistent

**Action**: Standardize logger names and use appropriate log levels

### 7. Add Input Validation
**Files**: All public functions

**Issue**: No validation of input parameters

**Action**: Add validation decorators or functions:
```python
def validate_metric_name(name: str) -> str:
    if not name or not name.strip():
        raise ValueError("Metric name cannot be empty")
    return name.strip()
```

### 8. Reduce Code Duplication in Core Classes
**Files**: `core/metrics_core.py`, `core/log_core.py`

**Issue**: Similar patterns for getting/creating instruments

**Action**: Extract common patterns to base class or utilities

---

## P1: Testing

### 9. Increase Test Coverage
**Files**: Currently has some tests but coverage could be improved

**Coverage Needed**:
- All core classes
- Decorators
- Control lifecycle hooks
- Calculator functions

### 10. Add Integration Tests
**Files**: Create `tests/integration/`

**Coverage**: Test actual OTEL SDK integration

### 11. Add Mock Fixtures
**Files**: Create `tests/fixtures/`

**Purpose**: Mock OTEL providers and exporters

### 12. Test Error Paths
**Files**: All test files

**Issue**: Error handling paths not well tested

**Action**: Add tests for error conditions

---

## P1: Documentation

### 13. Improve Docstrings
**Files**: All files, especially core classes

**Issue**: Some docstrings could be more detailed

**Action**: Add comprehensive docstrings with examples

### 14. Document Architecture
**Files**: Create `docs/ARCHITECTURE.md`

**Purpose**: Document the overall architecture and design decisions

### 15. Add API Documentation
**Files**: Create `docs/API.md`

**Purpose**: Comprehensive API documentation

---

## P2: Code Organization

### 16. Organize Core Classes Better
**Files**: `core/` directory

**Issue**: Large files, could be better organized

**Action**: Consider splitting if files get too large (>500 lines)

### 17. Extract Utilities
**Files**: Create `chaosotel/utils/`

**Purpose**: Common utilities for validation, formatting, etc.

### 18. Improve Import Organization
**Files**: All files

**Issue**: Imports not consistently organized

**Action**: Use isort and standardize

### 19. Create TypedDict for Config
**Files**: `otel.py`, `control.py`

**Purpose**: Type-safe configuration objects

---

## P2: Performance

### 20. Optimize Metric Recording
**Files**: `core/metrics_core.py`

**Issue**: May create instruments inefficiently

**Action**: Review and optimize instrument creation/caching

### 21. Optimize Span Creation
**Files**: `core/trace_core.py`

**Issue**: Span creation may be inefficient

**Action**: Review and optimize

### 22. Add Batch Operations
**Files**: `core/metrics_core.py`, `core/log_core.py`

**Purpose**: Support batch recording for better performance

---

## P2: Features

### 23. Add Configuration Validation
**Files**: `otel.py`

**Purpose**: Validate OTEL configuration before initialization

### 24. Add Health Checks
**Files**: Create `chaosotel/health.py`

**Purpose**: Health check functions for OTEL providers

### 25. Support Custom Exporters
**Files**: `otel.py`

**Purpose**: Easier integration of custom exporters

### 26. Add Metrics Aggregation
**Files**: `core/metrics_core.py`

**Purpose**: Support for metric aggregation strategies

---

## P3: Future Enhancements

### 27. Support Async Operations
**Files**: All core files

**Purpose**: Async/await support for better performance

### 28. Add Metrics Sampling
**Files**: `core/metrics_core.py`

**Purpose**: Configurable sampling for high-volume metrics

### 29. Support Multiple OTEL Versions
**Files**: All files

**Purpose**: Support multiple OTEL SDK versions

### 30. Add Plugin System
**Files**: Create `chaosotel/plugins/`

**Purpose**: Plugin system for custom integrations

---

## Implementation Phases

### Phase 1: Critical Fixes (P0)
1. Improve exception handling
2. Add type hints
3. Validate initialization

**Estimated Time**: 4-6 hours

### Phase 2: Code Quality (P1)
4. Extract magic numbers
5. Standardize errors
6. Add input validation
7. Reduce duplication

**Estimated Time**: 8-10 hours

### Phase 3: Testing (P1)
8. Increase coverage
9. Add integration tests
10. Test error paths

**Estimated Time**: 12-16 hours

### Phase 4: Organization (P2)
11. Extract utilities
12. Improve organization
13. Create TypedDicts

**Estimated Time**: 4-6 hours

### Phase 5: Performance (P2)
14. Optimize recording
15. Add batch operations

**Estimated Time**: 6-8 hours

---

## Code Review Checklist

- [ ] All P0 issues fixed
- [ ] Exception handling improved
- [ ] Type hints added
- [ ] Input validation added
- [ ] Tests added with good coverage
- [ ] Documentation updated
- [ ] Magic numbers extracted
- [ ] Error messages standardized
- [ ] Code duplication reduced

---

## Notes

- This is a core library, changes affect all extensions
- Maintain backward compatibility
- Test thoroughly with all extensions
- Document breaking changes clearly
- Consider semantic versioning for changes

