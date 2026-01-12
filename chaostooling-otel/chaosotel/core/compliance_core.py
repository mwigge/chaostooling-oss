# chaosotel/core/compliance_core.py

"""
ComplianceCore - Regulatory compliance tracking and audit trail.

Tracks compliance for:
- SOX (Sarbanes-Oxley) - Financial controls
- GDPR (Data Protection) - EU regulation
- PCI-DSS (Payment Security) - Card industry
- HIPAA (Healthcare) - Health data
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("chaosotel.compliance_core")


class Regulation(str, Enum):
    """Supported regulations."""

    SOX = "SOX"
    GDPR = "GDPR"
    PCI_DSS = "PCI-DSS"
    HIPAA = "HIPAA"


class ComplianceCore:
    """
    Core compliance tracking interface.

    Provides unified API for:
    - Compliance score calculation
    - Violation detection
    - Audit trail generation
    - Risk assessment

    Tracks 4 major regulations:
    - SOX (financial controls)
    - GDPR (data protection)
    - PCI-DSS (payment security)
    - HIPAA (healthcare data)
    """

    def __init__(self, regulations: Optional[List[str]] = None):
        """
        Initialize ComplianceCore.

        Args:
            regulations: List of regulations to track (default: all)
        """
        self.regulations = regulations or [r.value for r in Regulation]

        # Validation
        valid_regs = {r.value for r in Regulation}
        for reg in self.regulations:
            if reg not in valid_regs:
                logger.warning(f"Unknown regulation: {reg}")

        # Compliance state
        self._compliance_scores: Dict[str, float] = {
            reg: 100.0 for reg in self.regulations
        }
        self._violations: Dict[str, List[Dict[str, Any]]] = {
            reg: [] for reg in self.regulations
        }
        self._audit_trail: List[Dict[str, Any]] = []
        self._action_count: Dict[str, int] = {
            reg: 0 for reg in self.regulations
        }
        self._violation_count: Dict[str, int] = {
            reg: 0 for reg in self.regulations
        }

        logger.info(
            f"ComplianceCore initialized for regulations: {', '.join(self.regulations)}"
        )

    # ========================================================================
    # COMPLIANCE SCORE MANAGEMENT
    # ========================================================================

    def get_compliance_score(self, regulation: str) -> float:
        """
        Get compliance score for a regulation.

        Args:
            regulation: Regulation name

        Returns:
            Compliance score (0-100)
        """
        return self._compliance_scores.get(regulation, 50.0)

    def get_overall_score(self) -> float:
        """
        Get overall compliance score (average across all regulations).

        Returns:
            Overall compliance score (0-100)
        """
        if not self.regulations:
            return 100.0

        total = sum(
            self._compliance_scores.get(reg, 50.0) for reg in self.regulations
        )
        return total / len(self.regulations)

    def set_compliance_score(
        self, regulation: str, score: float, reason: Optional[str] = None
    ) -> None:
        """
        Set compliance score for a regulation.

        Args:
            regulation: Regulation name
            score: Score (0-100)
            reason: Reason for score
        """
        try:
            score = max(0.0, min(100.0, float(score)))
            old_score = self._compliance_scores.get(regulation, 100.0)
            self._compliance_scores[regulation] = score

            self._audit_trail.append(
                {
                    "event": "compliance_score_updated",
                    "regulation": regulation,
                    "old_score": old_score,
                    "new_score": score,
                    "reason": reason,
                    "timestamp": self._get_iso_timestamp(),
                }
            )

            logger.info(
                f"Updated {regulation} compliance score: {old_score} → {score}"
            )
        except Exception as e:
            logger.error(f"Error setting compliance score: {e}")

    # ========================================================================
    # VIOLATION TRACKING
    # ========================================================================

    def record_violation(
        self,
        regulation: str,
        violation: str,
        severity: str = "medium",
        details: Optional[Dict[str, Any]] = None,
        remediation: Optional[str] = None,
    ) -> None:
        """
        Record compliance violation.

        Args:
            regulation: Regulation that was violated
            violation: Description of violation
            severity: "low", "medium", "high", "critical"
            details: Additional details
            remediation: How to remediate
        """
        try:
            violation_entry = {
                "violation": violation,
                "severity": severity,
                "timestamp": self._get_iso_timestamp(),
                "details": details or {},
                "remediation": remediation,
            }

            if regulation not in self._violations:
                self._violations[regulation] = []

            self._violations[regulation].append(violation_entry)
            self._violation_count[regulation] = (
                self._violation_count.get(regulation, 0) + 1
            )

            # Impact score based on severity
            severity_impact = {
                "low": 2.0,
                "medium": 5.0,
                "high": 10.0,
                "critical": 20.0,
            }

            impact = severity_impact.get(severity, 5.0)
            current_score = self._compliance_scores.get(regulation, 100.0)
            new_score = max(0.0, current_score - impact)
            self._compliance_scores[regulation] = new_score

            self._audit_trail.append(
                {
                    "event": "violation_recorded",
                    "regulation": regulation,
                    "violation": violation,
                    "severity": severity,
                    "score_impact": impact,
                    "new_score": new_score,
                    "timestamp": self._get_iso_timestamp(),
                }
            )

            logger.warning(
                f"Recorded {severity} violation in {regulation}: {violation}"
            )
        except Exception as e:
            logger.error(f"Error recording violation: {e}")

    def get_violations(
        self, regulation: Optional[str] = None
    ) -> Dict[str, List]:
        """
        Get violations for regulation(s).

        Args:
            regulation: Specific regulation (or None for all)

        Returns:
            Dictionary of violations
        """
        if regulation:
            return {regulation: self._violations.get(regulation, [])}

        return self._violations.copy()

    def get_violation_count(self, regulation: Optional[str] = None) -> int:
        """
        Get violation count.

        Args:
            regulation: Specific regulation (or None for total)

        Returns:
            Violation count
        """
        if regulation:
            return self._violation_count.get(regulation, 0)

        return sum(self._violation_count.values())

    # ========================================================================
    # ACTION TRACKING
    # ========================================================================

    def track_action_execution(
        self,
        action_name: str,
        regulation: Optional[str] = None,
        status: str = "success",
        duration_ms: float = 0.0,
    ) -> None:
        """
        Track action execution for compliance purposes.

        Args:
            action_name: Name of action
            regulation: Specific regulation (or None for all)
            status: "success" or "error"
            duration_ms: Execution duration
        """
        try:
            regulations_to_track = (
                [regulation] if regulation else self.regulations
            )

            for reg in regulations_to_track:
                self._action_count[reg] = self._action_count.get(reg, 0) + 1

                self._audit_trail.append(
                    {
                        "event": "action_executed",
                        "regulation": reg,
                        "action": action_name,
                        "status": status,
                        "duration_ms": duration_ms,
                        "timestamp": self._get_iso_timestamp(),
                    }
                )

            logger.debug(f"Tracked action execution: {action_name} ({status})")
        except Exception as e:
            logger.error(f"Error tracking action execution: {e}")

    # ========================================================================
    # COMPLIANCE REPORT GENERATION
    # ========================================================================

    def generate_compliance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.

        Returns:
            Dictionary with compliance details
        """
        try:
            report = {
                "timestamp": self._get_iso_timestamp(),
                "overall_score": self.get_overall_score(),
                "regulations": {},
                "total_violations": self.get_violation_count(),
                "total_actions": sum(self._action_count.values()),
            }

            for reg in self.regulations:
                report["regulations"][reg] = {  # type: ignore[index]
                    "score": self.get_compliance_score(reg),
                    "violations": self.get_violation_count(reg),
                    "actions": self._action_count.get(reg, 0),
                    "violation_details": self.get_violations(reg).get(reg, []),
                }

            logger.info(
                f"Generated compliance report: score={report['overall_score']}"
            )

            return report
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {"error": str(e), "regulations": {}}

    # ========================================================================
    # AUDIT TRAIL
    # ========================================================================

    def get_audit_trail(
        self, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail entries.

        Args:
            limit: Maximum number of entries (or None for all)

        Returns:
            List of audit trail entries
        """
        if limit:
            return self._audit_trail[-limit:]

        return self._audit_trail.copy()

    def clear_audit_trail(self) -> None:
        """Clear audit trail."""
        self._audit_trail.clear()
        logger.info("Audit trail cleared")

    # ========================================================================
    # RISK ASSESSMENT
    # ========================================================================

    def get_compliance_risk_level(self) -> Dict[str, Any]:
        """
        Calculate compliance risk level based on scores and violations.

        Returns:
            Dictionary with risk level details
        """
        try:
            overall_score = self.get_overall_score()
            violation_count = self.get_violation_count()

            # Risk level calculation
            if overall_score >= 90:
                risk_level = 1
                risk_name = "Low"
            elif overall_score >= 75:
                risk_level = 2
                risk_name = "Medium"
            elif overall_score >= 50:
                risk_level = 3
                risk_name = "High"
            else:
                risk_level = 4
                risk_name = "Critical"

            # Adjust for violations
            if violation_count > 10:
                risk_level = min(4, risk_level + 1)
                risk_name = ["Low", "Medium", "High", "Critical"][
                    risk_level - 1
                ]

            return {
                "risk_level": risk_level,
                "risk_name": risk_name,
                "compliance_score": overall_score,
                "violation_count": violation_count,
            }
        except Exception as e:
            logger.error(f"Error calculating risk level: {e}")
            return {
                "risk_level": 2,
                "risk_name": "Unknown",
                "compliance_score": 50.0,
                "violation_count": 0,
            }

    # ========================================================================
    # REGULATION-SPECIFIC METHODS
    # ========================================================================

    def check_sox_compliance(self, action_name: str) -> bool:
        """Check SOX compliance for action."""
        return self.get_compliance_score("SOX") >= 75

    def check_gdpr_compliance(self, action_name: str) -> bool:
        """Check GDPR compliance for action."""
        return self.get_compliance_score("GDPR") >= 75

    def check_pci_dss_compliance(self, action_name: str) -> bool:
        """Check PCI-DSS compliance for action."""
        return self.get_compliance_score("PCI-DSS") >= 75

    def check_hipaa_compliance(self, action_name: str) -> bool:
        """Check HIPAA compliance for action."""
        return self.get_compliance_score("HIPAA") >= 75

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _get_iso_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def shutdown(self) -> None:
        """Shutdown compliance core."""
        try:
            logger.info("ComplianceCore shutdown")
        except Exception as e:
            logger.error(f"Error during ComplianceCore shutdown: {e}")
