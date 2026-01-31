#!/usr/bin/env python3
"""
DEPRECATED: This tool has been merged into baseline_manager.py

Please use baseline_manager.py instead:
    python baseline_manager.py validate --source database --all-systems

This file is kept for backward compatibility and will be removed in a future release.
"""

import sys
import warnings

warnings.warn(
    "validate_baseline_metrics.py is deprecated. Use 'baseline_manager.py validate' instead.",
    DeprecationWarning,
    stacklevel=2,
)

print("\n" + "=" * 80)
print("⚠️  DEPRECATION WARNING")
print("=" * 80)
print("This tool has been merged into baseline_manager.py")
print("\nPlease use instead:")
print("  python baseline_manager.py validate --source database --all-systems")
print("  python baseline_manager.py validate --source file --system postgres")
print("\nFor more options, run:")
print("  python baseline_manager.py validate --help")
print("=" * 80 + "\n")

sys.exit(1)
"""
Baseline Metrics Validation Script
Verifies that all baseline_metrics.json files are properly formatted and complete.
"""

import json
import sys
from pathlib import Path

# Configuration
EXPECTED_DATABASES = [
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "cassandra",
    "kafka",
    "rabbitmq",
    "mssql",
]
EXPERIMENTS_DIR = Path("/home/morgan/dev/src/chaostooling-oss/chaostooling-experiments")

# Required fields in each metric
REQUIRED_METRIC_FIELDS = [
    "query",
    "metric_type",
    "unit",
    "description",
    "baseline",
    "status",
    "valid_range",
]
REQUIRED_BASELINE_FIELDS = [
    "mean",
    "stdev",
    "min",
    "max",
    "percentile_50",
    "percentile_95",
    "percentile_99",
]
REQUIRED_RANGE_FIELDS = ["min", "max", "unit"]


class BaselineMetricsValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
        self.total_databases = 0
        self.databases_with_files = 0

    def validate_file_exists(self, db_name):
        """Check if baseline_metrics.json exists for database"""
        baseline_file = EXPERIMENTS_DIR / db_name / "baseline_metrics.json"
        return baseline_file.exists()

    def validate_json_syntax(self, file_path):
        """Validate JSON syntax"""
        try:
            with open(file_path, "r") as f:
                json.load(f)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON syntax error: {str(e)}"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    def validate_structure(self, data, db_name):
        """Validate baseline_metrics.json structure"""
        issues = []

        # Check top-level fields
        required_top_level = [
            "timestamp",
            "service_name",
            "phase",
            "datasource",
            "metrics",
        ]
        for field in required_top_level:
            if field not in data:
                issues.append(f"Missing top-level field: {field}")

        # Validate service_name matches database
        if "service_name" in data and data["service_name"] != db_name:
            issues.append(
                f"service_name mismatch: expected '{db_name}', got '{data['service_name']}'"
            )

        # Validate phase
        if data.get("phase") != "baseline_collection":
            issues.append(
                f"phase should be 'baseline_collection', got '{data.get('phase')}'"
            )

        # Validate datasource
        if data.get("datasource") != "prometheus":
            issues.append(
                f"datasource should be 'prometheus', got '{data.get('datasource')}'"
            )

        # Validate metrics structure
        if "metrics" not in data:
            issues.append("Missing 'metrics' section")
            return issues

        if not isinstance(data["metrics"], dict):
            issues.append("'metrics' must be a dictionary")
            return issues

        if len(data["metrics"]) == 0:
            issues.append("'metrics' dictionary is empty (at least 1 metric required)")
            return issues

        # Validate each metric
        for metric_name, metric_data in data["metrics"].items():
            if not isinstance(metric_data, dict):
                issues.append(f"Metric '{metric_name}': must be a dictionary")
                continue

            # Check required fields
            for field in REQUIRED_METRIC_FIELDS:
                if field not in metric_data:
                    issues.append(f"Metric '{metric_name}': missing field '{field}'")

            # Validate baseline statistics
            if "baseline" in metric_data:
                baseline = metric_data["baseline"]
                if not isinstance(baseline, dict):
                    issues.append(
                        f"Metric '{metric_name}': baseline must be a dictionary"
                    )
                else:
                    for field in REQUIRED_BASELINE_FIELDS:
                        if field not in baseline:
                            issues.append(
                                f"Metric '{metric_name}': baseline missing field '{field}'"
                            )
                        elif not isinstance(baseline[field], (int, float)):
                            issues.append(
                                f"Metric '{metric_name}': baseline.{field} must be numeric"
                            )

                    # Validate baseline ranges
                    if "min" in baseline and "max" in baseline:
                        if baseline["min"] < 0 and baseline["max"] > 0:
                            # Only warn if both negative and positive, which might be intentional
                            pass
                        elif baseline["min"] > baseline["max"]:
                            issues.append(f"Metric '{metric_name}': baseline min > max")

            # Validate valid_range
            if "valid_range" in metric_data:
                valid_range = metric_data["valid_range"]
                if not isinstance(valid_range, dict):
                    issues.append(
                        f"Metric '{metric_name}': valid_range must be a dictionary"
                    )
                else:
                    for field in REQUIRED_RANGE_FIELDS:
                        if field not in valid_range:
                            issues.append(
                                f"Metric '{metric_name}': valid_range missing field '{field}'"
                            )

        return issues

    def validate_database(self, db_name):
        """Validate baseline_metrics.json for a single database"""
        print(f"\nValidating {db_name}...", end=" ")
        self.total_databases += 1

        # Check file exists
        if not self.validate_file_exists(db_name):
            self.warnings.append(f"{db_name}: baseline_metrics.json not found")
            print("❌ NOT FOUND")
            return

        self.databases_with_files += 1
        baseline_file = EXPERIMENTS_DIR / db_name / "baseline_metrics.json"

        # Validate JSON syntax
        valid, error = self.validate_json_syntax(baseline_file)
        if not valid:
            self.errors.append(f"{db_name}: {error}")
            print(f"❌ SYNTAX ERROR: {error}")
            return

        # Load and validate structure
        try:
            with open(baseline_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.errors.append(f"{db_name}: Failed to load JSON: {str(e)}")
            print(f"❌ LOAD ERROR: {str(e)}")
            return

        issues = self.validate_structure(data, db_name)

        if issues:
            self.errors.extend([f"{db_name}: {issue}" for issue in issues])
            print(f"❌ VALIDATION ERRORS ({len(issues)})")
            for issue in issues:
                print(f"   - {issue}")
        else:
            num_metrics = len(data.get("metrics", {}))
            self.passed.append(f"{db_name}: {num_metrics} metrics")
            print(f"✅ VALID ({num_metrics} metrics)")

    def validate_all(self):
        """Validate all databases"""
        print("=" * 70)
        print("Baseline Metrics Validation Report")
        print("=" * 70)
        print(f"Checking databases: {', '.join(EXPECTED_DATABASES)}")
        print(f"Directory: {EXPERIMENTS_DIR}")

        for db_name in EXPECTED_DATABASES:
            self.validate_database(db_name)

        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total databases checked: {self.total_databases}")
        print(f"Files found: {self.databases_with_files}/{self.total_databases}")
        print(f"Valid files: {len(self.passed)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")

        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed:
                print(f"   ✓ {item}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   ! {warning}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   ✗ {error}")
            return False
        else:
            print("\n" + "=" * 70)
            print("✅ All validations passed!")
            print("=" * 70)
            return True


def main():
    validator = BaselineMetricsValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
