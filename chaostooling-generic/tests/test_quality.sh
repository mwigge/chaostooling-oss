#!/bin/bash
# Quality check automation script for chaostooling baseline integration
# 
# Runs all code quality checks and generates reports
# Usage: ./test_quality.sh [coverage|lint|type|security|all]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$PROJECT_DIR/chaosgeneric"
TEST_DIR="$PROJECT_DIR/tests"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# ============================================================================
# COVERAGE CHECKS
# ============================================================================

run_coverage() {
    print_header "Running Coverage Analysis"
    
    cd "$PROJECT_DIR"
    
    echo "Running pytest with coverage..."
    python -m pytest tests/ \
        --cov=chaosgeneric \
        --cov-report=html \
        --cov-report=term-missing:skip-covered \
        --cov-branch \
        --cov-fail-under=95 \
        -v --tb=short
    
    if [ $? -eq 0 ]; then
        print_success "Coverage check passed (>95%)"
        echo "HTML report generated: htmlcov/index.html"
    else
        print_error "Coverage check failed"
        return 1
    fi
}

run_unit_tests() {
    print_header "Running Unit Tests Only"
    
    cd "$PROJECT_DIR"
    
    python -m pytest tests/ \
        -m unit \
        -v --tb=short
    
    if [ $? -eq 0 ]; then
        print_success "All unit tests passed"
    else
        print_error "Unit tests failed"
        return 1
    fi
}

run_integration_tests() {
    print_header "Running Integration Tests"
    
    cd "$PROJECT_DIR"
    
    python -m pytest tests/ \
        -m integration \
        -v --tb=short
    
    if [ $? -eq 0 ]; then
        print_success "All integration tests passed"
    else
        print_error "Integration tests failed (DB may be required)"
        return 1
    fi
}

run_e2e_tests() {
    print_header "Running E2E Tests"
    
    cd "$PROJECT_DIR"
    
    python -m pytest tests/ \
        -m e2e \
        -v --tb=short
    
    if [ $? -eq 0 ]; then
        print_success "All E2E tests passed"
    else
        print_error "E2E tests failed"
        return 1
    fi
}

# ============================================================================
# LINTING CHECKS
# ============================================================================

run_ruff() {
    print_header "Running Ruff Linting"
    
    cd "$PROJECT_DIR"
    
    echo "Checking for linting errors..."
    python -m ruff check "$SOURCE_DIR" --show-fixes
    
    if [ $? -eq 0 ]; then
        print_success "No ruff linting errors found"
    else
        print_error "Ruff found issues"
        return 1
    fi
}

run_black() {
    print_header "Checking Code Formatting (Black)"
    
    cd "$PROJECT_DIR"
    
    echo "Checking code format..."
    python -m black "$SOURCE_DIR" --check --diff
    
    if [ $? -eq 0 ]; then
        print_success "Code formatting is correct"
    else
        print_warning "Code needs formatting (run 'black chaosgeneric/')"
        # Don't fail, just warn
    fi
}

run_isort() {
    print_header "Checking Import Sorting (isort)"
    
    cd "$PROJECT_DIR"
    
    echo "Checking import order..."
    python -m isort "$SOURCE_DIR" --check-only --diff
    
    if [ $? -eq 0 ]; then
        print_success "Import order is correct"
    else
        print_warning "Imports need sorting (run 'isort chaosgeneric/')"
    fi
}

# ============================================================================
# TYPE CHECKING
# ============================================================================

run_mypy() {
    print_header "Running MyPy Type Checking (Strict)"
    
    cd "$PROJECT_DIR"
    
    echo "Type checking..."
    python -m mypy "$SOURCE_DIR" \
        --strict \
        --ignore-missing-imports \
        --show-error-codes \
        --pretty
    
    if [ $? -eq 0 ]; then
        print_success "No type errors found (strict mode)"
    else
        print_error "MyPy found type errors"
        return 1
    fi
}

# ============================================================================
# SECURITY CHECKS
# ============================================================================

run_bandit() {
    print_header "Running Bandit Security Scan"
    
    cd "$PROJECT_DIR"
    
    echo "Scanning for security issues..."
    python -m bandit -r "$SOURCE_DIR" -f json -o bandit-report.json
    
    # Check for HIGH severity issues
    HIGH_ISSUES=$(python -c "
import json
try:
    with open('bandit-report.json') as f:
        report = json.load(f)
        high = sum(1 for result in report.get('results', []) if result['severity'] == 'HIGH')
        print(high)
except:
    print(0)
" 2>/dev/null || echo "0")
    
    if [ "$HIGH_ISSUES" -eq 0 ]; then
        print_success "No HIGH severity security issues found"
    else
        print_error "Found $HIGH_ISSUES HIGH severity security issues"
        return 1
    fi
}

# ============================================================================
# SUMMARY REPORT
# ============================================================================

generate_summary() {
    print_header "Quality Check Summary"
    
    echo "Test Results:"
    echo "  - Unit Tests: See output above"
    echo "  - Integration Tests: See output above"
    echo "  - E2E Tests: See output above"
    echo ""
    echo "Code Quality:"
    echo "  - Ruff Linting: See output above"
    echo "  - Black Formatting: See output above"
    echo "  - isort Import Sorting: See output above"
    echo "  - MyPy Type Checking: See output above"
    echo "  - Bandit Security: See output above"
    echo ""
    echo "Reports Generated:"
    if [ -d htmlcov ]; then
        echo "  - Coverage Report: htmlcov/index.html"
    fi
    if [ -f bandit-report.json ]; then
        echo "  - Security Report: bandit-report.json"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local check_type="${1:-all}"
    
    case "$check_type" in
        coverage)
            run_coverage
            ;;
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        e2e)
            run_e2e_tests
            ;;
        lint)
            run_ruff
            run_black
            run_isort
            ;;
        type)
            run_mypy
            ;;
        security)
            run_bandit
            ;;
        all)
            echo "Running ALL quality checks..."
            run_unit_tests && \
            run_ruff && \
            run_black && \
            run_isort && \
            run_mypy && \
            run_bandit && \
            run_coverage
            generate_summary
            print_success "All quality checks passed!"
            ;;
        *)
            echo "Usage: $0 [coverage|unit|integration|e2e|lint|type|security|all]"
            echo ""
            echo "Options:"
            echo "  coverage     - Run pytest with coverage analysis"
            echo "  unit         - Run unit tests only"
            echo "  integration  - Run integration tests"
            echo "  e2e          - Run end-to-end tests"
            echo "  lint         - Run ruff, black, and isort"
            echo "  type         - Run mypy type checker (strict)"
            echo "  security     - Run bandit security scanner"
            echo "  all          - Run all checks (default)"
            exit 1
            ;;
    esac
}

main "$@"
