# GitHub Actions Workflows

This directory contains GitHub Actions workflows for automated code quality checks and CI/CD.

## Workflows

### `ci.yml` - Main CI Pipeline
**Triggers:** Pull requests and pushes to main/master/develop branches

**Checks:**
- ✅ **Ruff** - Fast Python linter and formatter (blocking)
- ✅ **Black** - Code formatter (blocking)
- ✅ **isort** - Import statement sorter (blocking)
- ⚠️ **MyPy** - Type checker (non-blocking, warnings only)
- ⚠️ **Bandit** - Security linter (non-blocking, warnings only)

This is the primary workflow that runs on all pull requests. It ensures code quality and formatting standards are met before merging.

**Features:**
- GitHub annotations for easy error identification
- Artifact uploads for security reports
- Summary output in GitHub Actions UI
- Clear error messages with fix commands

## Running Checks Locally

Before pushing code, you can run the same checks locally:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run Ruff linter
ruff check .

# Run Ruff formatter
ruff format .

# Check Black formatting
black --check .

# Format with Black
black .

# Check isort
isort --check-only .

# Sort imports with isort
isort .

# Run MyPy type checking
mypy . --ignore-missing-imports

# Run Bandit security check
bandit -r . -ll
```

## Pre-commit Hooks

For automatic checks before committing, install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

This will run checks automatically on `git commit`.

## Fixing Issues

If the CI fails, you can fix issues automatically:

```bash
# Auto-fix Ruff issues
ruff check . --fix

# Auto-format with Ruff
ruff format .

# Auto-format with Black
black .

# Auto-sort imports
isort .
```

## Configuration

Linting tools are configured in:
- `pyproject.toml` - Project dependencies and tool configurations
- Individual package `pyproject.toml` files for sub-packages

## Notes

- **MyPy** and **Bandit** are non-blocking (warnings only) to allow gradual adoption
- All formatting checks (Black, Ruff format, isort) are blocking and must pass
- Ruff linter checks are blocking and must pass
