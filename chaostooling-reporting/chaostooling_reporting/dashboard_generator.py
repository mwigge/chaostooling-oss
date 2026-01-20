"""
Dashboard generator for Chaos Engineering experiments.

Generates Grafana dashboards for individual experiment runs using a template-based approach.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from string import Template

import requests

logger = logging.getLogger("chaostooling_reporting.dashboard_generator")


class DashboardGenerator:
    """Generate and provision Grafana dashboards for experiment runs."""

    def __init__(
        self,
        grafana_url: Optional[str] = None,
        api_key: Optional[str] = None,
        template_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize dashboard generator.

        Args:
            grafana_url: Grafana server URL (e.g., http://localhost:3000)
            api_key: Grafana API key for provisioning
            template_path: Path to dashboard template JSON
            output_dir: Directory to save generated dashboards (if not provisioning)
        """
        self.grafana_url = grafana_url or os.environ.get(
            "GRAFANA_URL", "http://localhost:3000"
        )
        self.api_key = api_key or os.environ.get("GRAFANA_API_KEY", "")
        self.output_dir = Path(output_dir or "./dashboards/generated")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load template
        if template_path:
            self.template_path = Path(template_path)
        else:
            # Default template path relative to this file
            module_dir = Path(__file__).parent.parent.parent
            self.template_path = (
                module_dir
                / "chaostooling-demo"
                / "dashboards"
                / "templates"
                / "experiment-run-template.json"
            )

        self.template = self._load_template()
        logger.info(
            f"DashboardGenerator initialized: grafana_url={self.grafana_url}, "
            f"template_path={self.template_path}"
        )

    def _load_template(self) -> Dict[str, Any]:
        """Load dashboard template from file."""
        try:
            if self.template_path.exists():
                with open(self.template_path, "r") as f:
                    return json.load(f)
            else:
                logger.warning(
                    f"Template not found at {self.template_path}, using minimal template"
                )
                return self._get_minimal_template()
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            return self._get_minimal_template()

    def _get_minimal_template(self) -> Dict[str, Any]:
        """Return a minimal dashboard template."""
        return {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "panels": [
                {
                    "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
                    "id": 1,
                    "options": {
                        "content": "# ${experiment_title}\n\n**ID:** ${experiment_id}",
                        "mode": "markdown",
                    },
                    "title": "",
                    "type": "text",
                }
            ],
            "schemaVersion": 38,
            "style": "dark",
            "tags": ["chaos", "experiment", "generated"],
            "templating": {"list": []},
            "time": {"from": "${start_time}", "to": "${end_time}"},
            "timezone": "browser",
            "title": "Experiment: ${experiment_title}",
            "uid": "exp-${experiment_id}",
            "version": 1,
        }

    def generate_dashboard(
        self,
        experiment_id: str,
        experiment_title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        systems: Optional[List[str]] = None,
        journal: Optional[Dict[str, Any]] = None,
        report_url: Optional[str] = None,
        provision: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a dashboard for an experiment run.

        Args:
            experiment_id: Unique experiment identifier
            experiment_title: Human-readable experiment title
            start_time: Experiment start timestamp
            end_time: Experiment end timestamp (defaults to now)
            systems: List of systems affected by the experiment
            journal: Chaos Toolkit journal with experiment results
            report_url: URL to the experiment report
            provision: Whether to provision to Grafana (default True)

        Returns:
            Dictionary with dashboard_uid, dashboard_url, and dashboard_json
        """
        if end_time is None:
            end_time = datetime.now()

        systems = systems or []
        systems_str = ", ".join(systems) if systems else "N/A"

        # Format timestamps for Grafana
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Create substitution variables
        variables = {
            "experiment_id": experiment_id,
            "experiment_title": experiment_title,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "systems": systems_str,
            "report_url": report_url or "",
        }

        # Generate dashboard JSON
        dashboard_json = self._apply_template(variables)

        # Add experiment metadata to dashboard
        if journal:
            dashboard_json = self._add_journal_data(dashboard_json, journal)

        # Create safe UID (max 40 chars, alphanumeric and dashes only)
        safe_id = re.sub(r"[^a-zA-Z0-9-]", "-", experiment_id)[:32]
        dashboard_uid = f"exp-{safe_id}"
        dashboard_json["uid"] = dashboard_uid

        result = {
            "dashboard_uid": dashboard_uid,
            "dashboard_json": dashboard_json,
            "dashboard_url": None,
            "local_path": None,
        }

        # Save locally
        local_path = self._save_locally(dashboard_json, experiment_id)
        result["local_path"] = str(local_path)

        # Provision to Grafana if requested
        if provision and self.api_key:
            try:
                dashboard_url = self._provision_to_grafana(dashboard_json)
                result["dashboard_url"] = dashboard_url
                logger.info(f"Dashboard provisioned: {dashboard_url}")
            except Exception as e:
                logger.warning(f"Failed to provision dashboard to Grafana: {e}")
                result["dashboard_url"] = None
        elif provision:
            logger.info("No API key provided, skipping Grafana provisioning")

        return result

    def _apply_template(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """Apply variables to template using string substitution."""
        # Convert template to string
        template_str = json.dumps(self.template)

        # Replace ${variable} patterns
        for key, value in variables.items():
            # Escape special regex characters in value
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
            template_str = template_str.replace(f"${{{key}}}", escaped_value)

        # Parse back to JSON
        return json.loads(template_str)

    def _add_journal_data(
        self, dashboard_json: Dict[str, Any], journal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add experiment journal data to dashboard annotations."""
        # Extract key events from journal
        events = []

        # Steady state hypothesis
        ssh_before = journal.get("steady_states", {}).get("before", {})
        if ssh_before:
            events.append(
                {
                    "time": journal.get("start"),
                    "text": f"Steady State Before: {'Passed' if ssh_before.get('steady_state_met') else 'Failed'}",
                    "tags": ["steady-state", "before"],
                }
            )

        ssh_after = journal.get("steady_states", {}).get("after", {})
        if ssh_after:
            events.append(
                {
                    "time": journal.get("end"),
                    "text": f"Steady State After: {'Passed' if ssh_after.get('steady_state_met') else 'Failed'}",
                    "tags": ["steady-state", "after"],
                }
            )

        # Add rollback info if present
        rollbacks = journal.get("rollbacks", [])
        if rollbacks:
            for rb in rollbacks:
                events.append(
                    {
                        "time": rb.get("start"),
                        "text": f"Rollback: {rb.get('activity', {}).get('name', 'Unknown')}",
                        "tags": ["rollback"],
                    }
                )

        # Store events as dashboard description for reference
        if events:
            event_summary = "; ".join([e["text"] for e in events])
            current_desc = dashboard_json.get("description", "")
            dashboard_json["description"] = f"{current_desc} | Events: {event_summary}"

        return dashboard_json

    def _save_locally(self, dashboard_json: Dict[str, Any], experiment_id: str) -> Path:
        """Save dashboard JSON to local file."""
        # Create safe filename
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", experiment_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"experiment_{safe_id}_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(dashboard_json, f, indent=2)

        logger.info(f"Dashboard saved locally: {filepath}")
        return filepath

    def _provision_to_grafana(self, dashboard_json: Dict[str, Any]) -> str:
        """
        Provision dashboard to Grafana via API.

        Returns:
            Dashboard URL
        """
        url = f"{self.grafana_url}/api/dashboards/db"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "dashboard": dashboard_json,
            "overwrite": True,
            "message": f"Auto-generated dashboard for experiment: {dashboard_json.get('title', 'Unknown')}",
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            dashboard_url = f"{self.grafana_url}{result.get('url', '')}"
            return dashboard_url
        else:
            raise Exception(
                f"Failed to provision dashboard: {response.status_code} - {response.text}"
            )

    def delete_dashboard(self, dashboard_uid: str) -> bool:
        """
        Delete a dashboard from Grafana.

        Args:
            dashboard_uid: Dashboard UID to delete

        Returns:
            True if deleted successfully
        """
        if not self.api_key:
            logger.warning("No API key provided, cannot delete dashboard")
            return False

        url = f"{self.grafana_url}/api/dashboards/uid/{dashboard_uid}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            response = requests.delete(url, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"Dashboard deleted: {dashboard_uid}")
                return True
            else:
                logger.warning(
                    f"Failed to delete dashboard: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Error deleting dashboard: {e}")
            return False

    def cleanup_old_dashboards(
        self, max_age_days: int = 30, max_count: int = 100
    ) -> int:
        """
        Clean up old generated dashboards.

        Args:
            max_age_days: Delete dashboards older than this
            max_count: Keep at most this many dashboards per experiment type

        Returns:
            Number of dashboards deleted
        """
        deleted = 0

        # Clean up local files
        if self.output_dir.exists():
            cutoff = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
            for filepath in self.output_dir.glob("experiment_*.json"):
                if filepath.stat().st_mtime < cutoff:
                    filepath.unlink()
                    deleted += 1
                    logger.debug(f"Deleted old dashboard file: {filepath}")

        logger.info(f"Cleaned up {deleted} old dashboard files")
        return deleted


def extract_systems_from_experiment(experiment: Dict[str, Any]) -> List[str]:
    """
    Extract system names from experiment definition.

    Args:
        experiment: Chaos Toolkit experiment definition

    Returns:
        List of system names (e.g., ['postgresql', 'kafka'])
    """
    systems = set()

    # Look through method activities
    method = experiment.get("method", [])
    for activity in method:
        provider = activity.get("provider", {})
        module = provider.get("module", "")

        # Extract system from module name
        if "postgres" in module.lower():
            systems.add("postgresql")
        elif "mysql" in module.lower():
            systems.add("mysql")
        elif "mongodb" in module.lower():
            systems.add("mongodb")
        elif "redis" in module.lower():
            systems.add("redis")
        elif "cassandra" in module.lower():
            systems.add("cassandra")
        elif "mssql" in module.lower():
            systems.add("mssql")
        elif "kafka" in module.lower():
            systems.add("kafka")
        elif "rabbitmq" in module.lower():
            systems.add("rabbitmq")
        elif "activemq" in module.lower():
            systems.add("activemq")

        # Also check activity name for hints
        name = activity.get("name", "").lower()
        for sys_name in [
            "postgresql",
            "postgres",
            "mysql",
            "mongodb",
            "redis",
            "cassandra",
            "mssql",
            "kafka",
            "rabbitmq",
            "activemq",
        ]:
            if sys_name in name:
                systems.add(sys_name.replace("postgres", "postgresql"))

    return sorted(list(systems))


def extract_timestamps_from_journal(
    journal: Dict[str, Any]
) -> tuple[datetime, datetime]:
    """
    Extract start and end timestamps from journal.

    Args:
        journal: Chaos Toolkit experiment journal

    Returns:
        Tuple of (start_time, end_time) as datetime objects
    """
    start_str = journal.get("start")
    end_str = journal.get("end")

    # Parse ISO format timestamps
    if start_str:
        try:
            start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            start_time = datetime.now()
    else:
        start_time = datetime.now()

    if end_str:
        try:
            end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except ValueError:
            end_time = datetime.now()
    else:
        end_time = datetime.now()

    return start_time, end_time
