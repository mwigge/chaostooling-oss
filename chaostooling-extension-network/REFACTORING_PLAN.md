# Refactoring Plan - chaostooling-extension-network

## Overview

This extension provides network chaos actions (latency, partition, DNS) and probes. Similar to compute extension, it's focused but needs improvements in error handling, type hints, and code organization.

## Priority Levels

- **P0 (Critical)**: Must fix
- **P1 (High)**: Should fix
- **P2 (Medium)**: Nice to have
- **P3 (Low)**: Future enhancements

---

## P0: Critical Issues

### 1. Add Type Hints
**Files**: All action and probe files

**Issue**: Functions lack comprehensive type hints

**Action**: Add type hints for all parameters and return values

### 2. Improve Error Handling
**Files**: `actions/network_latency.py`, `actions/network_partition.py`, `actions/network_dns.py`

**Issue**: Subprocess errors, network command failures not well handled

**Action**: Add specific exception types and better error messages

### 3. Add Input Validation
**Files**: All action files

**Issue**: No validation of network parameters (latency ranges, interface names, etc.)

**Action**: Add validation functions

### 4. Ensure Cleanup on Errors
**Files**: `actions/network_latency.py`, `actions/network_partition.py`

**Issue**: Network rules may not be cleaned up if errors occur

**Action**: Use context managers or try/finally to ensure cleanup

---

## P1: Code Quality

### 5. Extract Magic Numbers and Strings
**Files**: All files

**Issue**: Hardcoded values like default interfaces, timeout values

**Action**: Move to constants:
```python
class NetworkDefaults:
    DEFAULT_INTERFACE = "eth0"
    DEFAULT_TIMEOUT = 30
    MAX_LATENCY_MS = 10000
    MIN_LATENCY_MS = 0
```

### 6. Standardize Return Types
**Files**: All action files

**Issue**: Inconsistent return value structures

**Action**: Standardize on `dict[str, Any]` with consistent keys

### 7. Improve Subprocess Handling
**Files**: `actions/network_latency.py`, `actions/network_partition.py`

**Issue**: Subprocess calls need better error checking

**Action**: Add proper error handling and validation

### 8. Extract Common Network Command Logic
**Files**: All action files using `tc` or network commands

**Issue**: Similar patterns for executing network commands

**Action**: Create utility functions:
```python
def execute_tc_command(command: list[str], description: str) -> dict[str, Any]:
    # Common subprocess execution with error handling
```

### 9. Add Logging Consistency
**Files**: All files

**Issue**: Logger names inconsistent

**Action**: Use `logger = logging.getLogger(__name__)`

---

## P1: Testing

### 10. Add Unit Tests
**Files**: Create `tests/test_network_*.py`

**Coverage**: Test all network actions and probes

### 11. Add Integration Tests
**Files**: Create `tests/integration/`

**Coverage**: Test actual network manipulation (with safeguards)

### 12. Add Mock Fixtures
**Files**: Create `tests/fixtures/`

**Purpose**: Mock subprocess calls and network interfaces

---

## P1: Documentation

### 13. Improve Docstrings
**Files**: All files

**Issue**: Some docstrings need more detail

**Action**: Add comprehensive docstrings with examples

### 14. Document Network Requirements
**Files**: Create `docs/REQUIREMENTS.md`

**Purpose**: Document required tools (tc, iptables, etc.) and permissions

---

## P2: Code Organization

### 15. Separate Action Types
**Files**: Consider splitting large files

**Current**: `actions/network_latency.py` may be large

**Action**: Keep organized but consider if splitting helps

### 16. Create Network Command Utilities
**Files**: Create `chaosnetwork/utils/network_commands.py`

**Purpose**: Centralize network command execution

### 17. Improve Config Management
**Files**: `config.py`

**Issue**: Config could be more structured

**Action**: Use dataclasses or TypedDict

---

## P2: Features

### 18. Add Network Rule Validation
**Files**: `actions/network_latency.py`, `actions/network_partition.py`

**Purpose**: Validate network rules before applying

### 19. Add Rule Status Checking
**Files**: `actions/network_cleanup.py`

**Purpose**: Check if rules exist before cleanup

### 20. Support Multiple Network Interfaces
**Files**: All action files

**Purpose**: Better support for multiple interfaces

### 21. Add Network Monitoring
**Files**: `probes/network_metrics.py`

**Purpose**: Enhanced network metrics collection

---

## P3: Future Enhancements

### 22. Add Network Profiles
**Files**: Create `profiles.py`

**Purpose**: Predefined network chaos profiles

### 23. Support IPv6
**Files**: All network action files

**Purpose**: IPv6 support for network chaos

### 24. Add Bandwidth Limiting
**Files**: `actions/network_latency.py`

**Purpose**: More comprehensive bandwidth control

### 25. Add Observability Integration
**Files**: All files

**Purpose**: Better integration with chaosotel

---

## Implementation Phases

### Phase 1: Critical Fixes (P0)
1. Add type hints
2. Improve error handling
3. Add input validation
4. Ensure cleanup on errors

**Estimated Time**: 3-4 hours

### Phase 2: Code Quality (P1)
5. Extract magic numbers
6. Standardize return types
7. Extract common logic
8. Improve subprocess handling

**Estimated Time**: 4-6 hours

### Phase 3: Testing (P1)
9. Add unit tests
10. Add integration tests

**Estimated Time**: 6-8 hours

### Phase 4: Organization (P2)
11. Create utilities
12. Improve config

**Estimated Time**: 2-3 hours

---

## Code Review Checklist

- [ ] All P0 issues fixed
- [ ] Type hints added
- [ ] Error handling improved
- [ ] Input validation added
- [ ] Cleanup guaranteed
- [ ] Tests added
- [ ] Documentation updated
- [ ] Magic numbers extracted

---

## Notes

- Network manipulation requires root/sudo permissions
- Ensure proper cleanup to avoid leaving network in bad state
- Test thoroughly in isolated environments
- Document required system tools and permissions

