# Refactoring Summary - Quick Reference

## Immediate Actions (P0 - Critical)

1. **Remove unused import** (`jmeter_parser.py:13`)
   - Remove `import re` (not used)

2. **Fix markdown linting** (`README_JMETER_EXPERIMENT_GENERATOR.md`)
   - 18 warnings: add blank lines around lists, headings, code blocks

3. **Verify Python 3.9 compatibility**
   - Current type hints use `dict[str, Any]` (Python 3.9+)
   - Project requires 3.9+, so should be fine, but verify

## High Priority (P1)

### Code Quality
- **Error handling**: Replace generic `except Exception` with specific exceptions
- **Type hints**: Add TypedDict classes for structured data
- **Magic values**: Extract port numbers, service types to constants
- **Service detection**: Refactor long if-elif chain to registry pattern

### Testing
- Add unit tests for parser and generator
- Add integration tests for end-to-end flow
- Add sample JMeter test plan fixtures

### Documentation
- Fix all markdown linting warnings
- Add comprehensive docstrings
- Update API documentation

## Medium Priority (P2)

### Organization
- Extract service detection to separate module
- Extract scenario templates to configuration
- Create data models (TypedDicts)
- Improve logging consistency

### Features
- Add configuration file support
- Add experiment validation
- Optimize XML parsing if needed

## Quick Fixes

```bash
# Fix markdown linting
markdownlint README_JMETER_EXPERIMENT_GENERATOR.md --fix

# Remove unused import
# In jmeter_parser.py, remove line 13: import re

# Run linters
ruff check chaostooling-generic/chaosgeneric/actions/
ruff format chaostooling-generic/chaosgeneric/actions/
black chaostooling-generic/chaosgeneric/actions/
```

## Estimated Effort

- **P0 (Critical)**: 30 minutes
- **P1 (High)**: 4-6 hours
- **P2 (Medium)**: 6-8 hours
- **Total**: ~12-15 hours

See `REFACTORING_PLAN.md` for detailed breakdown.

