# Refactoring Plan - chaostooling-extension-compute

## Overview

This extension provides compute stress actions (CPU, memory, disk) and probes for system metrics. The codebase is relatively small and focused, but there are opportunities for improvement in error handling, type hints, and code organization.

## Priority Levels

- **P0 (Critical)**: Must fix - blocking issues
- **P1 (High)**: Should fix - code quality, maintainability
- **P2 (Medium)**: Nice to have - improvements
- **P3 (Low)**: Future enhancements

---

## P0: Critical Issues

### 1. Add Type Hints
**Files**: `actions/compute_stress.py`, `probes/compute_metrics.py`, `probes/compute_system.py`

**Issue**: Functions lack return type hints and some parameter type hints

**Action**: Add comprehensive type hints:
```python
def stress_cpu(
    duration: Optional[int] = None,
    load: Optional[int] = None,
    cores: Optional[int] = None,
) -> dict[str, Any]:
    # ...
```

### 2. Improve Error Handling
**Files**: `actions/compute_stress.py`

**Issue**: Generic exception handling, subprocess errors not well handled

**Action**: Add specific exception types and better error messages

### 3. Validate Input Parameters
**Files**: All action and probe files

**Issue**: No validation of input ranges (e.g., load 0-100, duration > 0)

**Action**: Add validation decorators or functions

---

## P1: Code Quality

### 4. Extract Magic Numbers
**Files**: `actions/compute_stress.py`, `config.py`

**Issue**: Hardcoded values like default durations, load percentages

**Action**: Move to constants or config:
```python
class ComputeDefaults:
    DEFAULT_CPU_DURATION = 10
    DEFAULT_CPU_LOAD = 100
    DEFAULT_MEMORY_DURATION = 10
    MAX_LOAD_PERCENTAGE = 100
```

### 5. Standardize Return Types
**Files**: `actions/compute_stress.py`

**Issue**: Some functions return `bool`, others return `dict`

**Action**: Standardize on `dict[str, Any]` with consistent structure:
```python
{
    "status": "success" | "error",
    "message": str,
    "duration": int,
    "cores": int,
    # ...
}
```

### 6. Improve Subprocess Error Handling
**Files**: `actions/compute_stress.py`

**Issue**: Subprocess calls may fail silently or with unclear errors

**Action**: Add proper error checking and informative error messages

### 7. Add Logging Consistency
**Files**: All files

**Issue**: Logger name inconsistent (`"chaostoolkit"` vs module-specific)

**Action**: Use `logger = logging.getLogger(__name__)`

### 8. Extract Common Stress Logic
**Files**: `actions/compute_stress.py`

**Issue**: CPU, memory, disk stress have similar patterns

**Action**: Create base stress function:
```python
def _execute_stress_command(
    command: list[str],
    duration: int,
    description: str,
) -> dict[str, Any]:
    # Common subprocess execution logic
```

---

## P1: Testing

### 9. Add Unit Tests
**Files**: Create `tests/test_compute_stress.py`, `tests/test_compute_metrics.py`

**Coverage**: Test all stress functions and probes

### 10. Add Integration Tests
**Files**: Create `tests/integration/`

**Coverage**: Test actual stress execution (with safeguards)

### 11. Add Mock Fixtures
**Files**: Create `tests/fixtures/`

**Purpose**: Mock subprocess calls and system metrics

---

## P1: Documentation

### 12. Improve Docstrings
**Files**: All files

**Issue**: Some docstrings could be more detailed

**Action**: Add comprehensive docstrings with examples

### 13. Add Usage Examples
**Files**: Create `docs/examples/`

**Purpose**: Provide examples for each stress type

---

## P2: Code Organization

### 14. Separate Stress Types
**Files**: `actions/compute_stress.py`

**Issue**: Large file with multiple stress types

**Action**: Consider splitting into:
- `actions/cpu_stress.py`
- `actions/memory_stress.py`
- `actions/disk_stress.py`

### 15. Create Stress Base Class
**Files**: Create `actions/base_stress.py`

**Purpose**: Common base class for all stress types

### 16. Improve Config Management
**Files**: `config.py`

**Issue**: Config could be more structured

**Action**: Use dataclasses or TypedDict for config

---

## P2: Features

### 17. Add Stress Validation
**Files**: `actions/compute_stress.py`

**Purpose**: Validate system can handle requested stress before applying

### 18. Add Stress Monitoring
**Files**: `actions/compute_stress.py`

**Purpose**: Monitor actual stress levels during execution

### 19. Add Graceful Degradation
**Files**: `actions/compute_stress.py`

**Purpose**: Handle cases where stress-ng is not available

### 20. Support Alternative Stress Tools
**Files**: `actions/compute_stress.py`

**Purpose**: Support multiple stress tools (stress, stress-ng, etc.)

---

## P3: Future Enhancements

### 21. Add Resource Limits
**Files**: `actions/compute_stress.py`

**Purpose**: Prevent excessive resource consumption

### 22. Add Stress Profiles
**Files**: Create `profiles.py`

**Purpose**: Predefined stress profiles (light, medium, heavy)

### 23. Add Observability Integration
**Files**: All files

**Purpose**: Better integration with chaosotel for metrics

---

## Implementation Phases

### Phase 1: Critical Fixes (P0)
1. Add type hints
2. Improve error handling
3. Add input validation

**Estimated Time**: 2-3 hours

### Phase 2: Code Quality (P1)
4. Extract magic numbers
5. Standardize return types
6. Improve subprocess handling
7. Extract common logic

**Estimated Time**: 4-6 hours

### Phase 3: Testing (P1)
8. Add unit tests
9. Add integration tests

**Estimated Time**: 6-8 hours

### Phase 4: Organization (P2)
10. Split large files
11. Create base classes

**Estimated Time**: 3-4 hours

---

## Code Review Checklist

- [ ] All P0 issues fixed
- [ ] Type hints added
- [ ] Error handling improved
- [ ] Input validation added
- [ ] Tests added
- [ ] Documentation updated
- [ ] Magic numbers extracted
- [ ] Return types standardized

---

## Notes

- This is a smaller codebase, refactoring should be straightforward
- Focus on safety (stress operations can be dangerous)
- Ensure proper cleanup of stress processes
- Add safeguards to prevent accidental system overload

