from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast


class ComplianceCore:
    """Compliance tracking integrated with execution"""

    REGULATORY_RULES = {
        "SOX": {
            "max_action_duration_ms": 5000,
            "min_recovery_rate": 0.95,
            "audit_trail_required": True,
        },
        "GDPR": {
            "max_data_exposure_ms": 300000,
            "encryption_required": True,
        },
        "PCI-DSS": {
            "max_downtime_ms": 60000,
            "audit_trail_required": True,
        },
    }

    def __init__(self, regulations=None):
        self.regulations = regulations or ["SOX"]
        self.execution_log = []
        self.violations = []

    def track_action_execution(
        self,
        action_name: str,
        target: str,
        target_type: str,
        severity: str,
        status: str,
        duration_ms: float,
        error: Optional[Exception] = None,
    ) -> None:
        """Track action for compliance reporting"""

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_name,
            "target": target,
            "target_type": target_type,
            "severity": severity,
            "status": status,
            "duration_ms": duration_ms,
            "error": str(error) if error else None,
        }

        self.execution_log.append(entry)

        # Check violations
        for regulation in self.regulations:
            violations = self.check_violations(regulation, entry)
            if violations:
                self.violations.extend(violations)

    def check_violations(self, regulation: str, action_entry: Dict) -> List[str]:
        """Check if action violates regulatory rules"""
        violations = []
        rules_dict = self.REGULATORY_RULES.get(regulation, {})
        rules: Dict[str, Any] = cast(Dict[str, Any], rules_dict)

        if "max_action_duration_ms" in rules:
            if action_entry["duration_ms"] > rules["max_action_duration_ms"]:
                violations.append(
                    f"{regulation}: Action {action_entry['action']} "
                    f"exceeded max duration ({action_entry['duration_ms']}ms > "
                    f"{rules['max_action_duration_ms']}ms)"
                )

        if "audit_trail_required" in rules and action_entry["status"] == "failed":
            if not action_entry.get("error"):
                violations.append(
                    f"{regulation}: No audit trail for failed action {action_entry['action']}"
                )

        return violations

    def generate_report(self) -> Dict:
        """Generate compliance report"""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regulations": self.regulations,
            "execution_log": self.execution_log,
            "violations": self.violations,
            "compliance_score": self._calculate_score(),
        }

    def _calculate_score(self) -> float:
        """Calculate overall compliance score (0-100)"""
        if not self.execution_log:
            return 100.0

        successful = sum(1 for e in self.execution_log if e["status"] == "success")
        total = len(self.execution_log)

        score = (successful / total) * 100
        violation_penalty = len(self.violations) * 10

        return max(0, score - violation_penalty)
