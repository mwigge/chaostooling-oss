# Refactoring and Cleanup Plan

## Overview

This document outlines the refactoring and cleanup tasks for the JMeter Experiment Generator feature. The plan is organized by priority and category.

## Priority Levels

- **P0 (Critical)**: Must fix before merge - blocking issues
- **P1 (High)**: Should fix soon - code quality and maintainability
- **P2 (Medium)**: Nice to have - improvements and optimizations
- **P3 (Low)**: Future enhancements - non-critical improvements

---

## P0: Critical Issues (Must Fix)

### 1. Remove Unused Imports
**Files**: `jmeter_parser.py`
- Remove unused `re` import (line 13)
- Verify all imports are actually used

**Action**:
```python
# Remove: import re
```

### 2. Fix Type Hints for Python 3.9 Compatibility
**Files**: All new files
- Current code uses `dict[str, Any]` which requires Python 3.9+
- Project supports Python 3.9+, but should verify compatibility
- Consider using `Dict[str, Any]` from `typing` if needed for older Python versions

**Action**: Verify Python 3.9 compatibility or add `from typing import Dict` if needed

### 3. Fix Markdown Linting Issues
**Files**: `README_JMETER_EXPERIMENT_GENERATOR.md`
- 18 markdown linting warnings (MD022, MD031, MD032, MD012)
- Fix blank lines around lists, headings, and code blocks

**Action**: Run markdown linter and fix all warnings

---

## P1: Code Quality and Structure

### 4. Improve Error Handling
**Files**: `jmeter_parser.py`, `experiment_generator.py`, `generate_experiment_from_jmeter.py`

**Issues**:
- Generic `except Exception` catches too broadly
- Missing specific exception types
- Error messages could be more informative

**Action**:
```python
# Instead of:
except Exception as e:
    logger.error(f"Failed to parse: {e}")
    raise

# Use:
except ET.ParseError as e:
    logger.error(f"Invalid XML structure: {e}")
    raise ValueError(f"Failed to parse JMeter XML: {e}") from e
except IOError as e:
    logger.error(f"File I/O error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error parsing test plan: {e}", exc_info=True)
    raise RuntimeError(f"Failed to parse JMeter test plan: {e}") from e
```

### 5. Add Type Hints for Return Types
**Files**: All new files

**Issues**:
- Some methods return complex dict structures without proper type hints
- Consider creating TypedDict classes for structured data

**Action**:
```python
from typing import TypedDict

class TestPlanMetadata(TypedDict):
    name: str
    description: str
    filename: str

class ThreadGroupConfig(TypedDict):
    name: str
    num_threads: int
    ramp_time: int
    duration: int
    loops: int
```

### 6. Extract Magic Numbers and Strings
**Files**: `jmeter_parser.py`, `experiment_generator.py`

**Issues**:
- Hardcoded values like port numbers (5432, 3306, 9092, etc.)
- Magic strings for service type detection
- Default values scattered throughout code

**Action**:
```python
# Create constants module or class
class ServiceDefaults:
    POSTGRES_PORT = 5432
    MYSQL_PORT = 3306
    KAFKA_PORT = 9092
    RABBITMQ_PORT = 5672
    DEFAULT_HTTP_PORT = 80
    DEFAULT_HTTPS_PORT = 443

class ServiceTypes:
    DATABASE_POSTGRES = "database_postgres"
    DATABASE_MYSQL = "database_mysql"
    # ... etc
```

### 7. Refactor Service Detection Logic
**Files**: `jmeter_parser.py` - `_identify_service()` method

**Issues**:
- Long if-elif chain is hard to maintain
- Service patterns could be configurable
- No way to extend with custom service types

**Action**:
```python
# Use a registry pattern
SERVICE_PATTERNS = {
    "database_postgres": ["postgres", "postgresql", "pg"],
    "database_mysql": ["mysql", "mariadb"],
    "database_mongodb": ["mongodb", "mongo"],
    # ... etc
}

def _identify_service(self, hostname: str) -> str:
    if not hostname:
        return "unknown"
    
    hostname_lower = hostname.lower()
    for service_type, patterns in SERVICE_PATTERNS.items():
        if any(pattern in hostname_lower for pattern in patterns):
            return service_type
    
    return "application"
```

### 8. Improve URL Building Logic
**Files**: `jmeter_parser.py` - `_build_url()` method

**Issues**:
- Complex conditional logic
- Protocol/port handling could be clearer
- Edge cases not well handled

**Action**: Refactor with clearer logic and better edge case handling

### 9. Reduce Code Duplication in Scenario Generation
**Files**: `experiment_generator.py`

**Issues**:
- `_generate_postgres_scenarios()`, `_generate_mysql_scenarios()`, etc. have similar structure
- Could use a template-based approach

**Action**:
```python
# Create scenario templates
SCENARIO_TEMPLATES = {
    "database_postgres": {
        "module": "chaosdb.actions.postgres.postgres_connection_stress",
        "func": "inject_connection_stress",
        "default_args": {"num_connections": 100},
    },
    # ... etc
}
```

---

## P1: Testing and Validation

### 10. Add Unit Tests
**Files**: Create `tests/test_jmeter_parser.py`, `tests/test_experiment_generator.py`

**Coverage Needed**:
- Test plan parsing with various XML structures
- Service type detection for all supported services
- URL building edge cases
- Experiment generation with different endpoint combinations
- Error handling paths

**Action**: Create comprehensive test suite following existing test patterns

### 11. Add Integration Tests
**Files**: Create `tests/test_integration_jmeter_experiment.py`

**Coverage Needed**:
- End-to-end flow: parse → generate → validate JSON
- Real JMeter test plan files (sample .jmx files)
- Generated experiment structure validation

### 12. Add Sample JMeter Test Plans
**Files**: Create `tests/fixtures/sample-test-plan.jmx`

**Purpose**: Provide test fixtures for testing parser with real JMeter XML

---

## P1: Documentation

### 13. Fix Markdown Linting
**Files**: `README_JMETER_EXPERIMENT_GENERATOR.md`

**Action**: Fix all 18 markdown linting warnings:
- Add blank lines around lists
- Add blank lines around headings
- Add blank lines around code blocks
- Remove multiple consecutive blank lines

### 14. Add Type Documentation
**Files**: All new Python files

**Action**: Add comprehensive docstrings with:
- Parameter types and descriptions
- Return type descriptions
- Example usage
- Raises sections for exceptions

### 15. Add API Documentation
**Files**: Update main README.md

**Action**: Ensure all public APIs are documented with examples

---

## P2: Code Organization

### 16. Extract Service Detection to Separate Module
**Files**: Create `chaosgeneric/actions/service_detector.py`

**Purpose**: Separate service detection logic for reusability and testability

**Action**:
```python
# Move _identify_service() and SERVICE_PATTERNS to new module
class ServiceDetector:
    @staticmethod
    def identify_service(hostname: str) -> str:
        # ... implementation
```

### 17. Extract Scenario Templates to Configuration
**Files**: Create `chaosgeneric/actions/scenario_templates.py`

**Purpose**: Make scenario generation configurable and extensible

**Action**: Move scenario generation logic to template-based system

### 18. Create Data Models/TypedDicts
**Files**: Create `chaosgeneric/actions/models.py`

**Purpose**: Define structured data types for parsed JMeter data and experiments

**Action**:
```python
from typing import TypedDict, List

class JMeterTestPlanData(TypedDict):
    test_plan: TestPlanMetadata
    thread_groups: List[ThreadGroupConfig]
    http_requests: List[HTTPRequest]
    endpoints: List[Endpoint]
    load_config: LoadConfig
```

### 19. Improve Logging Consistency
**Files**: All new files

**Issues**:
- Log levels may not be consistent
- Some operations lack logging
- Error context could be richer

**Action**: Standardize logging with appropriate levels and context

---

## P2: Performance and Optimization

### 20. Optimize XML Parsing
**Files**: `jmeter_parser.py`

**Issues**:
- Multiple `findall()` calls may traverse tree multiple times
- Could cache parsed elements

**Action**: Consider caching or single-pass parsing if performance is an issue

### 21. Optimize Endpoint Deduplication
**Files**: `jmeter_parser.py` - `_extract_endpoints()`

**Issues**:
- Calls `_extract_http_requests()` which may be expensive
- Could be optimized if called multiple times

**Action**: Cache HTTP requests if needed

---

## P2: Feature Enhancements

### 22. Add Configuration File Support
**Files**: New `chaosgeneric/actions/jmeter_config.py`

**Purpose**: Allow users to configure:
- Custom service detection patterns
- Custom scenario templates
- Default chaos parameters

**Action**: Create YAML/JSON config file support

### 23. Add Validation for Generated Experiments
**Files**: `experiment_generator.py`

**Purpose**: Validate generated experiment JSON against Chaos Toolkit schema

**Action**: Add validation step before writing experiment file

### 24. Support Custom Scenario Providers
**Files**: `experiment_generator.py`

**Purpose**: Allow users to provide custom scenario generation functions

**Action**: Add plugin/extension point for custom scenarios

---

## P3: Future Enhancements

### 25. Add CLI Command
**Files**: Create `chaosgeneric/cli/jmeter_experiment.py`

**Purpose**: Command-line tool for generating experiments

**Action**:
```bash
chaos-generate-jmeter-experiment /path/to/test-plan.jmx --output /path/to/output.json
```

### 26. Add JMeter Test Plan Validation
**Files**: `jmeter_parser.py`

**Purpose**: Validate JMeter test plan structure before parsing

**Action**: Add schema validation or basic structure checks

### 27. Support Gatling Test Plans
**Files**: New `gatling_parser.py`

**Purpose**: Extend feature to support Gatling simulations

**Action**: Create similar parser for Gatling Scala files

### 28. Add Experiment Customization Hooks
**Files**: `experiment_generator.py`

**Purpose**: Allow post-generation customization of experiments

**Action**: Add hooks/callbacks for experiment modification

---

## Implementation Order

### Phase 1: Critical Fixes (P0)
1. Remove unused imports
2. Fix markdown linting
3. Verify Python 3.9 compatibility

### Phase 2: Code Quality (P1 - High Priority)
4. Improve error handling
5. Add type hints and TypedDicts
6. Extract magic numbers/strings
7. Refactor service detection
8. Fix markdown documentation

### Phase 3: Testing (P1)
9. Add unit tests
10. Add integration tests
11. Add sample test fixtures

### Phase 4: Organization (P2)
12. Extract service detection module
13. Extract scenario templates
14. Create data models
15. Improve logging

### Phase 5: Enhancements (P2-P3)
16. Add configuration support
17. Add validation
18. Add CLI command
19. Future enhancements

---

## Code Review Checklist

Before submitting refactored code, ensure:

- [ ] All P0 issues fixed
- [ ] All linter errors resolved (ruff, black, isort)
- [ ] Type hints added where appropriate
- [ ] Error handling improved
- [ ] Tests added with good coverage
- [ ] Documentation updated
- [ ] No unused imports
- [ ] Magic numbers/strings extracted
- [ ] Code follows project style guidelines
- [ ] All functions have docstrings
- [ ] Examples work correctly

---

## Notes

- Follow existing code patterns in the codebase
- Maintain backward compatibility where possible
- Update documentation as code changes
- Run all tests before committing
- Use existing logging patterns
- Follow CLAUDE.md guidelines for observability integration

