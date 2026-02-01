"""
Report generator for Chaos Engineering experiments.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chaostooling_reporting")


class ReportGenerator:
    """Generate reports from experiment journals."""

    def __init__(
        self,
        output_dir: str = "./reports",
        formats: Optional[list[str]] = None,
        templates: Optional[dict[str, bool]] = None,
    ):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to save reports
            formats: List of output formats (html, pdf, json, csv)
            templates: Dictionary of template flags (executive, compliance, audit, etc.)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Tracking file for experiment run statistics
        self.tracking_file = self.output_dir / "experiment_runs.json"

        self.formats = formats or ["html", "json"]
        self.templates = templates or {
            "executive": True,
            "compliance": True,
            "audit": True,
            "product_owner": True,
        }

        logger.info(
            f"ReportGenerator initialized: output_dir={output_dir}, formats={self.formats}"
        )

    def generate_reports(
        self,
        experiment: dict[str, Any],
        journal: dict[str, Any],
        configuration: dict[str, Any],
    ) -> dict[str, str]:
        """
        Generate all requested reports.

        Returns:
            Dictionary mapping report type to file path
        """
        reports = {}

        # CRITICAL: Use experiment definition from journal (what was actually executed)
        # The journal contains the exact experiment definition that was run, which is
        # important for accurate counts of scenarios and activities.
        # This ensures reports work correctly for all experiments (kafka-chaos-experiment.json,
        # e2e-experiment.json, etc.) by always using the actual executed experiment definition.
        journal_experiment = journal.get("experiment", {})

        # Prioritize journal experiment definition (what was actually executed)
        # The journal's experiment dict contains the full experiment definition including "method"
        if journal_experiment and isinstance(journal_experiment, dict):
            # Check if journal has the method field (full experiment definition)
            if "method" in journal_experiment:
                # Journal has complete experiment definition - use it
                experiment = journal_experiment
                logger.debug(
                    f"Using experiment definition from journal: "
                    f"{experiment.get('title', 'unknown')} "
                    f"({len(experiment.get('method', []))} method steps)"
                )
            elif journal_experiment.get("title") and not experiment.get("method"):
                # Journal has partial definition but parameter is missing method - merge them
                experiment = {**experiment, **journal_experiment}
                logger.debug("Merged experiment definition from journal with parameter")
        elif not experiment.get("method") and journal_experiment:
            # Parameter doesn't have method, try journal as fallback
            experiment = journal_experiment
            logger.debug(
                "Using experiment definition from journal (fallback - parameter missing method)"
            )

        # Log which experiment is being used for transparency
        if experiment.get("method"):
            method_count = len(experiment.get("method", []))
            scenario_count = len(
                [
                    s
                    for s in experiment.get("method", [])
                    if s.get("name", "").startswith("SCENARIO-")
                ]
            )
            logger.info(
                f"Report will use experiment: {experiment.get('title', 'unknown')} "
                f"({scenario_count} scenarios, {method_count} total activities)"
            )

        # Generate unique experiment ID
        # 1. Try journal experiment ID (if Chaos Toolkit generated one)
        experiment_id = journal.get("experiment", {}).get("id")

        # 2. Generate UUID-based ID if not present
        if not experiment_id:
            # Create unique ID: experiment-title-hash + timestamp + short-uuid
            experiment_title = experiment.get("title", "chaos-experiment")
            title_hash = abs(hash(experiment_title)) % 10000  # 4-digit hash
            short_uuid = str(uuid.uuid4())[:8]  # First 8 chars of UUID
            timestamp_short = datetime.now().strftime("%Y%m%d%H%M%S")
            experiment_id = f"{title_hash:04d}-{timestamp_short}-{short_uuid}"

        # Store experiment ID in journal for future reference
        if "experiment" not in journal:
            journal["experiment"] = {}
        journal["experiment"]["id"] = experiment_id

        # Generate filename using experiment_id (matches experiment run) with optional title prefix
        # This ensures the report filename matches the actual experiment run identifier
        experiment_title = experiment.get("title", "")
        if experiment_title:
            # Create a short, filename-friendly version of the title (max 30 chars for prefix)
            title_prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", experiment_title.lower())
            title_prefix = re.sub(r"-+", "-", title_prefix)
            title_prefix = title_prefix.strip("-")[:30]
            # Use experiment_id as the primary identifier (matches experiment run)
            filename_id = f"{title_prefix}_{experiment_id}"
        else:
            # Use experiment_id directly if no title
            filename_id = experiment_id

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{filename_id}_{timestamp}"

        # Store experiment metadata for tracking
        self._store_experiment_run(experiment_id, experiment, journal, configuration)

        # Generate JSON report (always available)
        if "json" in self.formats:
            json_path = self._generate_json_report(experiment, journal, base_filename)
            reports["json"] = json_path

        # Generate HTML reports
        if "html" in self.formats:
            if self.templates.get("executive"):
                exec_path = self._generate_executive_report(
                    experiment, journal, base_filename
                )
                reports["executive_html"] = exec_path

            if self.templates.get("compliance"):
                comp_path = self._generate_compliance_report(
                    experiment, journal, base_filename
                )
                reports["compliance_html"] = comp_path

            if self.templates.get("audit"):
                audit_path = self._generate_audit_report(
                    experiment, journal, base_filename
                )
                reports["audit_html"] = audit_path

            if self.templates.get("product_owner"):
                po_path = self._generate_product_owner_report(
                    experiment, journal, base_filename
                )
                reports["product_owner_html"] = po_path

        # Generate PDF reports
        if "pdf" in self.formats:
            # PDF generation will be implemented later
            logger.info("PDF generation not yet implemented")

        # Generate CSV reports
        if "csv" in self.formats:
            csv_path = self._generate_csv_report(experiment, journal, base_filename)
            reports["csv"] = csv_path

        return reports

    def _generate_json_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate JSON report."""
        output_path = self.output_dir / f"{base_filename}_report.json"

        report_data = {
            "experiment": {
                "id": journal.get("experiment", {}).get("id"),
                "title": experiment.get("title"),
                "description": experiment.get("description"),
                "tags": experiment.get("tags", []),
            },
            "execution": {
                "start": journal.get("start"),
                "end": journal.get("end"),
                "duration": journal.get("duration"),
                "status": journal.get("status"),
            },
            "steady_state": journal.get("steady_state", {}),
            "run": journal.get("run", []),
            "rollbacks": journal.get("rollbacks", []),
            "deviations": journal.get("deviations", []),
        }

        with open(output_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"Generated JSON report: {output_path}")
        return str(output_path)

    def _generate_executive_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate executive summary HTML report."""
        output_path = self.output_dir / f"{base_filename}_executive.html"

        # Extract key metrics
        status = journal.get("status", "unknown")
        steady_state = journal.get("steady_state", {})
        run = journal.get("run", [])

        # Get experiment ID
        experiment_id = journal.get("experiment", {}).get("id", "N/A")

        # Get run statistics
        run_stats = self._get_experiment_run_stats(experiment.get("title", ""))

        # Generate test state/coverage
        test_state_coverage = self._generate_test_state_coverage(
            run, steady_state, experiment, journal
        )

        # Generate summary of all tests run
        tests_summary = self._generate_tests_summary(run)

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Executive Summary - {experiment.get("title", "Chaos Experiment")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .status-success {{ color: #27ae60; }}
        .status-failed {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <h1>Executive Summary</h1>
    <div class="summary">
        <h2>{experiment.get("title", "Chaos Experiment")}</h2>
        <p><strong>Experiment ID:</strong> {experiment_id}</p>
        <p><strong>Execution Date:</strong> {journal.get("start", "N/A")}</p>
        <p><strong>Status:</strong> <span class="status-{"success" if status == "completed" else "failed"}">{status}</span></p>
        {("<p><strong>Total Runs:</strong> " + str(run_stats.get("total_runs", 0)) + "</p>") if run_stats.get("total_runs", 0) > 0 else ""}
        {("<p><strong>Success Rate:</strong> " + f"{run_stats.get('success_rate', 0):.1f}% ({run_stats.get('successful_runs', 0)}/{run_stats.get('total_runs', 0)})" + "</p>") if run_stats.get("total_runs", 0) > 0 else ""}
    </div>

    {test_state_coverage}

    {tests_summary}
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Generated executive report: {output_path}")
        return str(output_path)

    def _generate_compliance_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate compliance report."""
        output_path = self.output_dir / f"{base_filename}_compliance.html"

        # Extract compliance-relevant data
        status = journal.get("status", "unknown")
        steady_state = journal.get("steady_state", {})
        run = journal.get("run", [])

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Compliance Report - {experiment.get("title", "Chaos Experiment")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #34495e; color: white; }}
        .status-passed {{ color: #27ae60; font-weight: bold; }}
        .status-failed {{ color: #e74c3c; font-weight: bold; }}
        .probe-detail {{ margin: 10px 0; padding: 10px; background: #fff; border-left: 4px solid #e74c3c; }}
        .probe-detail.passed {{ border-left-color: #27ae60; }}
        .suggestion {{ margin: 10px 0; padding: 10px; background: #fff3cd; border-left: 4px solid #f39c12; border-radius: 3px; }}
        .suggestion ul {{ margin: 5px 0; padding-left: 20px; }}
        .error-detail {{ font-family: monospace; font-size: 0.9em; color: #856404; background: #fff3cd; padding: 5px; border-radius: 3px; margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>Compliance Report</h1>
    <div class="section">
        <h2>Experiment Information</h2>
        <p><strong>Experiment ID:</strong> {journal.get("experiment", {}).get("id", "N/A")}</p>
        <p><strong>Title:</strong> {experiment.get("title", "N/A")}</p>
        <p><strong>Execution Date:</strong> {journal.get("start", "N/A")}</p>
        <p><strong>Status:</strong> {status}</p>
    </div>

    <div class="section">
        <h2>Testing Summary</h2>
        <p>This experiment demonstrates systematic testing of system resilience.</p>

        {self._generate_test_state_coverage(run, steady_state, experiment, journal)}

        {self._generate_scenario_summary(run)}

        {self._generate_steady_state_details(steady_state, experiment)}
    </div>

    {self._generate_scenario_details(run)}

    <div class="section">
        <h2>Evidence</h2>
        <p>Complete experiment journal available in JSON format.</p>
        <p><strong>Journal Path:</strong> Available via experiment execution logs</p>
    </div>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Generated compliance report: {output_path}")
        return str(output_path)

    def _generate_audit_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate audit trail report."""
        output_path = self.output_dir / f"{base_filename}_audit.html"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Audit Trail - {experiment.get("title", "Chaos Experiment")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .audit-entry {{ margin: 15px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #3498db; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>Audit Trail</h1>
    <div class="audit-entry">
        <div class="timestamp">Experiment Start: {journal.get("start", "N/A")}</div>
        <p><strong>Action:</strong> Experiment initiated</p>
        <p><strong>Experiment ID:</strong> {journal.get("experiment", {}).get("id", "N/A")}</p>
    </div>
"""

        # Add entries for each activity
        for activity_entry in journal.get("run", []):
            # Handle both nested (activity.activity) and flat structures
            activity = activity_entry.get("activity", activity_entry)
            activity_name = activity.get("name", activity_entry.get("name", "unknown"))
            activity_type = activity.get("type", activity_entry.get("type", "unknown"))
            activity_status = activity_entry.get("status", "unknown")
            activity_output = activity_entry.get("output", {})

            html_content += f"""
    <div class="audit-entry">
        <div class="timestamp">Activity: {activity_name}</div>
        <p><strong>Type:</strong> {activity_type}</p>
        <p><strong>Status:</strong> {activity_status}</p>
        <p><strong>Output:</strong> {json.dumps(activity_output, indent=2, default=str)}</p>
    </div>
"""

        html_content += f"""
    <div class="audit-entry">
        <div class="timestamp">Experiment End: {journal.get("end", "N/A")}</div>
        <p><strong>Action:</strong> Experiment completed</p>
        <p><strong>Final Status:</strong> {journal.get("status", "N/A")}</p>
        <p><strong>Duration:</strong> {journal.get("duration", 0):.2f} seconds</p>
    </div>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Generated audit report: {output_path}")
        return str(output_path)

    def _generate_product_owner_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate product owner report."""
        output_path = self.output_dir / f"{base_filename}_product_owner.html"

        # Categorize activities into: End-to-End Tests, Application Tests, Infrastructure Components
        run = journal.get("run", [])
        e2e_tests: dict[str, dict[str, Any]] = {}  # test_name -> {activities, total, successful, failed}
        application_tests: dict[str, dict[str, Any]] = {}  # test_name -> {activities, total, successful, failed}
        infrastructure_components: dict[str, dict[str, Any]] = {}  # component_name -> {activities, total, successful, failed, component_type}

        # Extract and categorize activities
        for activity_entry in run:
            # Handle both nested (activity.activity) and flat structures
            activity = activity_entry.get("activity", activity_entry)
            name = activity.get("name", activity_entry.get("name", ""))
            activity_type = activity.get("type", activity_entry.get("type", "unknown"))
            activity_status = activity_entry.get("status", "unknown")
            provider = activity.get("provider", {})
            provider_module = provider.get("module", "")
            provider_func = provider.get("func", "")

            # Skip SCENARIO actions themselves (they're organizational)
            if name.startswith("SCENARIO-"):
                continue

            # Identify end-to-end tests (distributed transaction tests, end-to-end flows)
            name_lower = name.lower()
            is_e2e = (
                "distributed-transaction" in name_lower
                or (
                    "transaction" in name_lower
                    and (
                        "test" in name_lower
                        or "verify" in name_lower
                        or "under" in name_lower
                    )
                )
                or (
                    "test" in name_lower
                    and (
                        "distributed" in name_lower
                        or "e2e" in name_lower
                        or "end-to-end" in name_lower
                    )
                )
                or (
                    "verify" in name_lower
                    and (
                        "transaction" in name_lower
                        or "data-consistency" in name_lower
                        or "baseline" in name_lower
                    )
                )
            )

            if is_e2e:
                test_name = name

                if test_name not in e2e_tests:
                    e2e_tests[test_name] = {
                        "activities": [],
                        "total": 0,
                        "successful": 0,
                        "failed": 0,
                    }

                e2e_tests[test_name]["activities"].append(
                    {
                        "name": name,
                        "type": activity_type,
                        "status": activity_status,
                    }
                )
                e2e_tests[test_name]["total"] += 1
                if activity_status == "succeeded":
                    e2e_tests[test_name]["successful"] += 1
                else:
                    e2e_tests[test_name]["failed"] += 1
            # Identify application tests
            elif "test" in name_lower and (
                "app" in name_lower
                or "application" in name_lower
                or "service" in name_lower
            ):
                test_name = name

                if test_name not in application_tests:
                    application_tests[test_name] = {
                        "activities": [],
                        "total": 0,
                        "successful": 0,
                        "failed": 0,
                    }

                application_tests[test_name]["activities"].append(
                    {
                        "name": name,
                        "type": activity_type,
                        "status": activity_status,
                    }
                )
                application_tests[test_name]["total"] += 1
                if activity_status == "succeeded":
                    application_tests[test_name]["successful"] += 1
                else:
                    application_tests[test_name]["failed"] += 1
            else:
                # Infrastructure component identification
                component_name = self._extract_component_name(
                    name=name,
                    provider_module=provider_module,
                    provider_func=provider_func,
                    activity_type=activity_type,
                )

                if component_name:
                    # Group messaging systems together (Kafka, RabbitMQ, etc.)
                    if component_name.lower() in [
                        "kafka",
                        "rabbitmq",
                        "activemq",
                        "nats",
                        "pulsar",
                    ]:
                        component_name = "Messaging Systems"

                    if component_name not in infrastructure_components:
                        infrastructure_components[component_name] = {
                            "activities": [],
                            "total": 0,
                            "successful": 0,
                            "failed": 0,
                            "component_type": self._infer_component_type(
                                component_name, provider_module
                            ),
                        }

                    infrastructure_components[component_name]["activities"].append(
                        {
                            "name": name,
                            "type": activity_type,
                            "status": activity_status,
                        }
                    )
                    infrastructure_components[component_name]["total"] += 1
                    if activity_status == "succeeded":
                        infrastructure_components[component_name]["successful"] += 1
                    else:
                        infrastructure_components[component_name]["failed"] += 1

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Product Owner Report - {experiment.get("title", "Chaos Experiment")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .service {{ margin: 15px 0; padding: 20px; background: #ecf0f1; border-radius: 5px; border-left: 4px solid #3498db; }}
        .service-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .service-name {{ font-size: 1.2em; font-weight: bold; color: #2c3e50; }}
        .resilience-score {{ font-size: 1.5em; font-weight: bold; padding: 10px 20px; border-radius: 5px; }}
        .score-high {{ background: #27ae60; color: white; }}
        .score-medium {{ background: #f39c12; color: white; }}
        .score-low {{ background: #e74c3c; color: white; }}
        .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 15px 0; }}
        .metric-box {{ background: white; padding: 10px; border-radius: 3px; }}
        .metric-label {{ font-size: 0.9em; color: #7f8c8d; }}
        .metric-value {{ font-size: 1.3em; font-weight: bold; color: #2c3e50; }}
        .activities-list {{ margin-top: 15px; }}
        .activity {{ padding: 5px; margin: 3px 0; background: white; border-radius: 3px; font-size: 0.9em; }}
        .activity-success {{ border-left: 3px solid #27ae60; }}
        .activity-failed {{ border-left: 3px solid #e74c3c; }}
        .no-services {{ padding: 20px; background: #fff3cd; border-radius: 5px; color: #856404; }}
    </style>
</head>
<body>
    <h1>Product Owner Report</h1>
    <p><strong>Experiment:</strong> {experiment.get("title", "N/A")}</p>
    <p><strong>Execution Date:</strong> {journal.get("start", "N/A")}</p>
    <p><strong>Overall Status:</strong> {journal.get("status", "unknown")}</p>

    <h2>Testing Coverage</h2>
"""

        # Generate sections for each category
        html_content += self._generate_test_category_section(
            "End-to-End Tests", e2e_tests
        )
        html_content += self._generate_test_category_section(
            "Application Tests", application_tests
        )
        html_content += self._generate_test_category_section(
            "Infrastructure Components", infrastructure_components
        )

        if not e2e_tests and not application_tests and not infrastructure_components:
            html_content += """
    <div class="no-services">
        <p><strong>No test activities detected in experiment.</strong></p>
        <p>Tests are automatically categorized as End-to-End Tests, Application Tests, or Infrastructure Components.</p>
    </div>
"""

        html_content += """
    <h2>Recommendations</h2>
    <div class="service">
        <h3>Resilience Assessment</h3>
        <p>Infrastructure components with resilience scores below 80% should be reviewed for:</p>
        <ul>
            <li>Error handling and retry mechanisms</li>
            <li>Timeout configurations</li>
            <li>Circuit breaker patterns</li>
            <li>Graceful degradation strategies</li>
            <li>Network resilience (latency, partition tolerance)</li>
            <li>Database failover and replication health</li>
            <li>Messaging system reliability</li>
            <li>API endpoint availability and response times</li>
        </ul>

        <h3>Next Steps</h3>
        <ul>
            <li>Review detailed traces in Grafana Tempo for failed activities</li>
            <li>Analyze error patterns in experiment logs</li>
            <li>Consider implementing additional resilience patterns for low-scoring components</li>
            <li>Run targeted chaos experiments for specific infrastructure components</li>
            <li>Review network, compute, database, and messaging system configurations</li>
        </ul>
    </div>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Generated product owner report: {output_path}")
        return str(output_path)

    def _generate_csv_report(
        self, experiment: dict[str, Any], journal: dict[str, Any], base_filename: str
    ) -> str:
        """Generate CSV report."""
        import csv

        output_path = self.output_dir / f"{base_filename}_activities.csv"

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Type", "Name", "Status", "Output"])

            for activity_entry in journal.get("run", []):
                # Handle both nested (activity.activity) and flat structures
                activity = activity_entry.get("activity", activity_entry)
                activity_type = activity.get("type", activity_entry.get("type", ""))
                activity_name = activity.get("name", activity_entry.get("name", ""))
                activity_status = activity_entry.get("status", "")
                activity_output = activity_entry.get("output", {})

                writer.writerow(
                    [
                        activity_type,
                        activity_name,
                        activity_status,
                        json.dumps(activity_output, default=str),
                    ]
                )

        logger.info(f"Generated CSV report: {output_path}")
        return str(output_path)

    def _store_experiment_run(
        self,
        experiment_id: str,
        experiment: dict[str, Any],
        journal: dict[str, Any],
        configuration: dict[str, Any],
    ) -> None:
        """Store experiment run information for tracking and statistics."""
        try:
            # Load existing runs
            runs_data = {}
            if self.tracking_file.exists():
                try:
                    with open(self.tracking_file) as f:
                        runs_data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    runs_data = {}

            experiment_title = experiment.get("title", "Unknown Experiment")

            # Initialize experiment entry if not exists
            if experiment_title not in runs_data:
                runs_data[experiment_title] = {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "runs": [],
                }

            # Add this run
            run_status = journal.get("status", "unknown")

            # Determine success: experiment is successful if:
            # 1. Status is "completed" AND
            # 2. All steady state probes passed (if any exist) AND
            # 3. All activities in the method succeeded (or at least no critical failures)

            is_success = False
            if run_status == "completed":
                # Check steady state probes
                steady_state = journal.get("steady_state", {})
                probes = steady_state.get("probes", [])

                # If no probes in journal, try experiment definition
                if not probes:
                    experiment_steady_state = experiment.get(
                        "steady-state-hypothesis", {}
                    ) or experiment.get("steady_state_hypothesis", {})
                    probes = experiment_steady_state.get("probes", [])

                # Check if all probes passed
                all_probes_passed = True
                if probes:
                    all_probes_passed = all(
                        probe.get("tolerance", False) for probe in probes
                    )
                else:
                    # If no probes defined, don't fail based on steady state
                    all_probes_passed = True

                # Check if all activities succeeded
                run = journal.get("run", [])
                all_activities_succeeded = True
                failed_activities = []
                if run:
                    for activity_entry in run:
                        # Handle both nested and flat structures
                        activity = activity_entry.get("activity", activity_entry)
                        activity_name = activity.get(
                            "name", activity_entry.get("name", "unknown")
                        )
                        activity_status = activity_entry.get("status", "unknown")

                        # Skip steady state probes in activity count (they're checked separately)
                        if (
                            activity_name.startswith("probe-")
                            and "steady" in activity_name.lower()
                        ):
                            continue

                        if activity_status not in ["succeeded", "success"]:
                            all_activities_succeeded = False
                            failed_activities.append(activity_name)
                else:
                    # If no activities, don't fail based on activities
                    all_activities_succeeded = True

                # Experiment is successful if:
                # - All activities succeeded (primary indicator), OR
                # - Status is completed and initial steady state passed (even if final steady state failed)
                # The rationale: In chaos engineering, if all chaos activities executed successfully,
                # the experiment succeeded in testing resilience, even if the system didn't fully recover
                is_success = all_activities_succeeded or (
                    run_status == "completed" and all_probes_passed
                )

                # Log for debugging
                if not is_success:
                    logger.debug(
                        f"Experiment marked as failed: activities_succeeded={all_activities_succeeded}, "
                        f"probes_passed={all_probes_passed}, failed_activities={failed_activities}"
                    )

            run_entry = {
                "experiment_id": experiment_id,
                "run_timestamp": journal.get("start", datetime.now().isoformat()),
                "status": run_status,
                "success": is_success,
                "duration": journal.get("duration", 0),
            }

            runs_data[experiment_title]["runs"].append(run_entry)
            runs_data[experiment_title]["total_runs"] += 1

            if is_success:
                runs_data[experiment_title]["successful_runs"] += 1
            else:
                runs_data[experiment_title]["failed_runs"] += 1

            # Keep only last 1000 runs per experiment to avoid file bloat
            if len(runs_data[experiment_title]["runs"]) > 1000:
                runs_data[experiment_title]["runs"] = runs_data[experiment_title][
                    "runs"
                ][-1000:]

            # Save updated runs
            with open(self.tracking_file, "w") as f:
                json.dump(runs_data, f, indent=2, default=str)

            logger.debug(
                f"Stored experiment run: {experiment_id} for {experiment_title}"
            )

        except Exception as e:
            logger.warning(f"Failed to store experiment run tracking: {e}")

    def _get_experiment_run_stats(self, experiment_title: str) -> dict[str, Any]:
        """Get statistics for an experiment based on run history."""
        try:
            if not self.tracking_file.exists():
                return {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "success_rate": 0.0,
                }

            with open(self.tracking_file) as f:
                runs_data = json.load(f)

            if experiment_title not in runs_data:
                return {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "success_rate": 0.0,
                }

            stats = runs_data[experiment_title]
            total = stats.get("total_runs", 0)
            successful = stats.get("successful_runs", 0)

            success_rate = (successful / total * 100) if total > 0 else 0.0

            return {
                "total_runs": total,
                "successful_runs": successful,
                "failed_runs": stats.get("failed_runs", 0),
                "success_rate": success_rate,
            }

        except Exception as e:
            logger.warning(f"Failed to get experiment run statistics: {e}")
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
            }

    def _extract_component_name(
        self, name: str, provider_module: str, provider_func: str, activity_type: str
    ) -> Optional[str]:
        """
        Extract component name from activity information (generic, decoupled approach).

        This method works with any infrastructure type by analyzing:
        - Activity names
        - Provider module paths
        - Function names

        Returns None if no component can be identified.
        """
        # Try to extract from provider module path (most reliable)
        if provider_module:
            module_parts = provider_module.split(".")
            # Look for common patterns: chaosdb.probes.postgres -> postgres
            # or chaosdb.actions.kafka -> kafka
            for part in reversed(module_parts):
                if part not in [
                    "probes",
                    "actions",
                    "chaosdb",
                    "chaos",
                    "db",
                    "system",
                    "network",
                    "compute",
                ]:
                    if len(part) > 2:  # Ignore very short parts
                        return part

        # Try to extract from function name
        if provider_func:
            func_parts = provider_func.split("_")
            for part in func_parts:
                if part not in [
                    "probe",
                    "action",
                    "check",
                    "status",
                    "connectivity",
                    "validate",
                ]:
                    if len(part) > 2:
                        return part

        # Try to extract from activity name (fallback)
        if name:
            name_lower = name.lower()
            # Look for common infrastructure patterns (but don't hardcode specific services)
            # Extract any word that looks like a component name
            import re

            # Match patterns like "probe-postgres-primary" or "action-kafka-connectivity"
            parts = re.split(r"[-_\s]+", name_lower)
            for part in parts:
                if part not in [
                    "probe",
                    "action",
                    "check",
                    "status",
                    "primary",
                    "replica",
                    "site",
                    "a",
                    "b",
                ]:
                    if len(part) > 2:
                        return part

        return None

    def _infer_component_type(self, component_name: str, provider_module: str) -> str:
        """
        Infer the type of infrastructure component (generic classification).

        Returns: "Database", "Messaging", "Network", "Compute", "API", "Load Balancer", "Unknown"
        """
        name_lower = component_name.lower()
        module_lower = provider_module.lower() if provider_module else ""

        # Database systems
        db_keywords = [
            "postgres",
            "mysql",
            "mongo",
            "redis",
            "cassandra",
            "oracle",
            "mssql",
            "sqlite",
        ]
        if any(
            keyword in name_lower or keyword in module_lower for keyword in db_keywords
        ):
            return "Database"

        # Messaging systems
        mq_keywords = ["kafka", "rabbitmq", "activemq", "nats", "pulsar", "sqs"]
        if any(
            keyword in name_lower or keyword in module_lower for keyword in mq_keywords
        ):
            return "Messaging"

        # Load balancers / Proxies
        lb_keywords = ["haproxy", "nginx", "traefik", "envoy", "proxy", "balancer"]
        if any(
            keyword in name_lower or keyword in module_lower for keyword in lb_keywords
        ):
            return "Load Balancer"

        # Network components
        network_keywords = ["network", "latency", "partition", "dns", "tcp", "http"]
        if any(
            keyword in name_lower or keyword in module_lower
            for keyword in network_keywords
        ):
            return "Network"

        # Compute / Application servers
        compute_keywords = [
            "app",
            "server",
            "service",
            "compute",
            "pod",
            "container",
            "vm",
        ]
        if any(
            keyword in name_lower or keyword in module_lower
            for keyword in compute_keywords
        ):
            return "Application/Compute"

        # API / External services
        api_keywords = ["api", "http", "rest", "graphql", "gateway"]
        if any(
            keyword in name_lower or keyword in module_lower for keyword in api_keywords
        ):
            return "API/External Service"

        return "Unknown"

    def _generate_steady_state_details(
        self, steady_state: dict[str, Any], experiment: dict[str, Any]
    ) -> str:
        """
        Generate detailed steady state validation information with failure details and suggestions.
        """
        # Try to get probes from journal steady_state first
        probes = steady_state.get("probes", [])

        # If not found in journal, try to get from experiment definition as fallback
        if not probes:
            experiment_steady_state = experiment.get(
                "steady-state-hypothesis", {}
            ) or experiment.get("steady_state_hypothesis", {})
            probes = experiment_steady_state.get("probes", [])

        if not probes:
            # Check if steady state hypothesis exists but has no probes
            has_hypothesis = bool(
                experiment.get("steady-state-hypothesis")
                or experiment.get("steady_state_hypothesis")
                or steady_state.get("title")
            )
            if has_hypothesis:
                return '<p><strong>Steady State Validation:</strong> <span class="status-failed">Hypothesis defined but no probes configured</span></p>'
            else:
                return '<p><strong>Steady State Validation:</strong> <span class="status-failed">No steady state hypothesis defined</span></p>'

        # Check overall status
        all_passed = all(probe.get("tolerance", False) for probe in probes)
        status_class = "status-passed" if all_passed else "status-failed"
        status_text = "Passed" if all_passed else "Failed"

        html = f'<p><strong>Steady State Validation:</strong> <span class="{status_class}">{status_text}</span></p>'

        if not all_passed:
            html += "<h3>Failed Probes</h3>"

            failed_probes = [p for p in probes if not p.get("tolerance", False)]
            for probe in failed_probes:
                probe_name = probe.get("name", "Unknown Probe")
                probe_output = probe.get("output", {})
                probe_status = probe.get("status", "unknown")
                probe_activity = probe.get("activity", {})
                probe_provider = (
                    probe_activity.get("provider", {}) if probe_activity else {}
                )

                # Extract error information
                error_msg = None
                if isinstance(probe_output, dict):
                    error_msg = (
                        probe_output.get("error")
                        or probe_output.get("exception")
                        or probe_output.get("message")
                    )
                elif isinstance(probe_output, str):
                    error_msg = probe_output

                # Determine probe type for suggestions
                provider_type = probe_provider.get("type", "")
                provider_module = probe_provider.get("module", "")
                provider_func = probe_provider.get("func", "")

                html += f"""
    <div class="probe-detail">
        <h4>{probe_name}</h4>
        <p><strong>Status:</strong> <span class="status-failed">{probe_status}</span></p>
        <p><strong>Type:</strong> {provider_type or "Unknown"}</p>
"""

                if error_msg:
                    html += f"""
        <div class="error-detail">
            <strong>Error Details:</strong><br/>
            {self._format_error_message(error_msg)}
        </div>
"""

                # Add suggestions based on probe type and error
                suggestions = self._generate_suggestions(
                    probe_name=probe_name,
                    provider_type=provider_type,
                    provider_module=provider_module,
                    provider_func=provider_func,
                    error_msg=error_msg,
                    probe_output=probe_output,
                )

                if suggestions:
                    html += """
        <div class="suggestion">
            <strong>Suggestions:</strong>
            <ul>
"""
                    for suggestion in suggestions:
                        html += f"                <li>{suggestion}</li>\n"
                    html += "            </ul>\n        </div>\n"

                html += "    </div>\n"

        # Show passed probes summary
        passed_probes = [p for p in probes if p.get("tolerance", False)]
        if passed_probes:
            html += f"<h3>Passed Probes ({len(passed_probes)}/{len(probes)})</h3>"
            for probe in passed_probes:
                probe_name = probe.get("name", "Unknown Probe")
                html += f'<div class="probe-detail passed"><strong>{probe_name}</strong> - Passed</div>\n'

        return html

    def _format_error_message(self, error_msg: Any) -> str:
        """Format error message for display."""
        if isinstance(error_msg, dict):
            # Try to extract meaningful error information
            error_str = (
                error_msg.get("message", "")
                or error_msg.get("error", "")
                or str(error_msg)
            )
            if error_str:
                return error_str.replace("\n", "<br/>")
        elif isinstance(error_msg, str):
            return error_msg.replace("\n", "<br/>")
        return str(error_msg)

    def _generate_suggestions(
        self,
        probe_name: str,
        provider_type: str,
        provider_module: str,
        provider_func: str,
        error_msg: Any,
        probe_output: Any,
    ) -> list[str]:
        """
        Generate suggestions based on probe failure type and error message.
        """
        suggestions = []
        name_lower = probe_name.lower()
        module_lower = provider_module.lower() if provider_module else ""
        error_str = str(error_msg).lower() if error_msg else ""

        # Database connectivity failures
        if (
            "postgres" in module_lower
            or "postgres" in name_lower
            or "mysql" in module_lower
            or "mongo" in module_lower
            or "redis" in module_lower
        ):
            if (
                "authentication" in error_str
                or "password" in error_str
                or "credential" in error_str
            ):
                suggestions.append("Verify database credentials are correct")
                suggestions.append("Check user permissions and access rights")
            elif "timeout" in error_str:
                suggestions.append("Increase connection timeout values")
                suggestions.append("Check database load and resource utilization")
                suggestions.append("Review network latency between services")
            elif (
                "connection" in error_str
                or "connect" in error_str
                or "refused" in error_str
            ):
                suggestions.append("Verify database service is running and accessible")
                suggestions.append("Check network connectivity and firewall rules")
                suggestions.append("Verify database credentials and permissions")
                suggestions.append("Check database connection pool settings")

        # HTTP/API probe failures
        elif provider_type == "http" or "http" in name_lower:
            if "connection" in error_str or "refused" in error_str:
                suggestions.append(
                    "Verify the service is running and listening on the expected port"
                )
                suggestions.append("Check service health endpoint is accessible")
                suggestions.append("Review load balancer and proxy configurations")
            elif "timeout" in error_str:
                suggestions.append("Increase HTTP timeout values")
                suggestions.append("Check service response times and performance")
                suggestions.append("Review network latency and bandwidth")
            elif "404" in error_str or "not found" in error_str:
                suggestions.append("Verify the endpoint URL is correct")
                suggestions.append("Check service routing and path configurations")
            elif "500" in error_str or "502" in error_str or "503" in error_str:
                suggestions.append("Check service logs for internal errors")
                suggestions.append("Review service resource utilization (CPU, memory)")
                suggestions.append("Verify dependent services are healthy")

        # Kafka/RabbitMQ messaging failures
        elif (
            "kafka" in module_lower
            or "kafka" in name_lower
            or "rabbitmq" in module_lower
        ):
            if "connection" in error_str or "broker" in error_str:
                suggestions.append("Verify messaging broker is running and accessible")
                suggestions.append("Check broker network connectivity")
                suggestions.append("Review broker configuration and cluster status")
            elif "timeout" in error_str:
                suggestions.append("Increase messaging system timeout values")
                suggestions.append("Check broker load and performance")
            elif "topic" in error_str or "queue" in error_str:
                suggestions.append("Verify topic/queue exists and is accessible")
                suggestions.append("Check topic/queue permissions and ACLs")

        # Generic connectivity/timeout failures
        if "timeout" in error_str and not suggestions:
            suggestions.append("Review timeout configurations for the probe")
            suggestions.append("Check network connectivity and latency")
            suggestions.append("Verify target service is responsive")

        if "connection" in error_str and not suggestions:
            suggestions.append("Verify target service is running and accessible")
            suggestions.append("Check network connectivity and firewall rules")
            suggestions.append("Review service configuration and endpoints")

        # General suggestions if no specific ones found
        if not suggestions:
            suggestions.append("Review experiment logs for detailed error information")
            suggestions.append(
                "Verify all required services are running before experiment execution"
            )
            suggestions.append(
                "Check experiment configuration and environment variables"
            )
            suggestions.append("Review steady-state hypothesis tolerance values")

        return suggestions

    def _group_activities_by_scenario(
        self, run: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group activities by SCENARIO.
        Returns a dictionary mapping scenario names to their activities.
        """
        scenarios: dict[str, list[dict[str, Any]]] = {}
        current_scenario = "Baseline/Other"

        for activity_entry in run:
            # Handle both nested (activity.activity) and flat structures
            activity = activity_entry.get("activity", activity_entry)
            activity_name = activity.get("name", activity_entry.get("name", "unknown"))
            activity_type = activity.get("type", activity_entry.get("type", "unknown"))
            activity_status = activity_entry.get("status", "unknown")

            # Check if this is a SCENARIO action
            if activity_name.startswith("SCENARIO-"):
                current_scenario = activity_name
                if current_scenario not in scenarios:
                    scenarios[current_scenario] = []
                # Include the SCENARIO action itself
                scenarios[current_scenario].append(
                    {
                        "name": activity_name,
                        "type": activity_type,
                        "status": activity_status,
                        "entry": activity_entry,
                    }
                )
            else:
                # Add to current scenario
                if current_scenario not in scenarios:
                    scenarios[current_scenario] = []
                scenarios[current_scenario].append(
                    {
                        "name": activity_name,
                        "type": activity_type,
                        "status": activity_status,
                        "entry": activity_entry,
                    }
                )

        return scenarios

    def _generate_test_state_coverage(
        self,
        run: list[dict[str, Any]],
        steady_state: dict[str, Any],
        experiment: dict[str, Any],
        journal: dict[str, Any],
    ) -> str:
        """
        Generate Test State/Coverage metric as an initial overview.
        """
        # If run is empty, try to extract from experiment definition as fallback
        if not run or len(run) == 0:
            # Extract activities from experiment method steps
            method_steps = experiment.get("method", []) or []
            # Reconstruct run-like structure from method steps
            run = []
            for step in method_steps:
                if isinstance(step, dict):
                    # Handle both action and probe types
                    if "action" in step:
                        run.append(
                            {
                                "activity": step.get("action", {}),
                                "type": "action",
                                "status": "unknown",  # Can't determine from definition
                                "name": step.get("action", {}).get("name", "unknown"),
                            }
                        )
                    elif "probe" in step:
                        run.append(
                            {
                                "activity": step.get("probe", {}),
                                "type": "probe",
                                "status": "unknown",  # Can't determine from definition
                                "name": step.get("probe", {}).get("name", "unknown"),
                            }
                        )

        scenarios = self._group_activities_by_scenario(run)

        # Calculate planned counts from experiment definition (always from actual experiment.json)
        # This ensures counts match the experiment file being executed, not hardcoded values
        method_steps = experiment.get("method", []) or []
        if not method_steps:
            # Fallback: try to get from journal if experiment definition is incomplete
            method_steps = journal.get("experiment", {}).get("method", []) or []

        planned_scenarios = [
            step
            for step in method_steps
            if step.get("name", "").startswith("SCENARIO-")
        ]
        planned_scenario_count = len(planned_scenarios)
        # Count all method steps as planned activities (includes scenarios, actions, and probes)
        planned_activity_count = len(method_steps)

        # Calculate overall metrics (executed counts)
        # Filter out SCENARIO actions themselves when counting activities (they're just markers)
        actual_activities = [
            activity_entry
            for activity_entry in run
            if not (
                activity_entry.get("activity", {})
                .get("name", "")
                .startswith("SCENARIO-")
                or activity_entry.get("name", "").startswith("SCENARIO-")
            )
        ]
        total_activities = len(actual_activities)
        successful_activities = sum(
            1
            for activity_entry in actual_activities
            if activity_entry.get("status") in ["succeeded", "success"]
        )
        overall_success_rate = (
            (successful_activities / total_activities * 100)
            if total_activities > 0
            else 0.0
        )

        # Count executed scenarios - count all scenarios, not just those starting with "SCENARIO-"
        # But exclude the "Baseline/Other" default scenario if it's empty
        scenario_count = len(
            [
                s
                for s in scenarios.keys()
                if s != "Baseline/Other" or len(scenarios.get(s, [])) > 0
            ]
        )

        # Count steady state probes
        probes = steady_state.get("probes", [])
        if not probes:
            experiment_steady_state = experiment.get(
                "steady-state-hypothesis", {}
            ) or experiment.get("steady_state_hypothesis", {})
            probes = experiment_steady_state.get("probes", [])

        probe_count = len(probes)
        passed_probes = (
            sum(1 for probe in probes if probe.get("tolerance", False)) if probes else 0
        )

        # Determine overall test state
        if overall_success_rate == 100.0 and passed_probes == probe_count:
            test_state = "Complete Success"
            state_class = "status-passed"
        elif overall_success_rate >= 80.0:
            test_state = "Mostly Successful"
            state_class = "status-passed"
        elif overall_success_rate >= 50.0:
            test_state = "Partially Successful"
            state_class = ""
        else:
            test_state = "Needs Attention"
            state_class = "status-failed"

        # Calculate coverage percentages
        scenario_coverage = (
            (scenario_count / planned_scenario_count * 100)
            if planned_scenario_count > 0
            else 0.0
        )
        activity_coverage = (
            (total_activities / planned_activity_count * 100)
            if planned_activity_count > 0
            else 0.0
        )

        html = f"""
    <div style="background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0;">
        <h3 style="margin-top: 0;">Test State / Coverage</h3>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 15px 0;">
            <div style="background: white; padding: 15px; border-radius: 5px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #2c3e50;">{
            overall_success_rate:.1f}%</div>
                <div style="color: #7f8c8d; font-size: 0.9em;">Overall Success Rate</div>
            </div>
            <div style="background: white; padding: 15px; border-radius: 5px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #2c3e50;">{
            scenario_count
        }{
            f"/{planned_scenario_count}"
            if planned_scenario_count > scenario_count
            else ""
        }</div>
                <div style="color: #7f8c8d; font-size: 0.9em;">Scenarios Tested{
            " (Executed/Planned)" if planned_scenario_count > scenario_count else ""
        }</div>
                {
            f'<div style="color: #95a5a6; font-size: 0.8em; margin-top: 5px;">Coverage: {scenario_coverage:.1f}%</div>'
            if planned_scenario_count > scenario_count
            else ""
        }
            </div>
            <div style="background: white; padding: 15px; border-radius: 5px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #2c3e50;">{
            total_activities
        }{
            f"/{planned_activity_count}"
            if planned_activity_count > total_activities
            else ""
        }</div>
                <div style="color: #7f8c8d; font-size: 0.9em;">Total Activities{
            " (Executed/Planned)" if planned_activity_count > total_activities else ""
        }</div>
                {
            f'<div style="color: #95a5a6; font-size: 0.8em; margin-top: 5px;">Coverage: {activity_coverage:.1f}%</div>'
            if planned_activity_count > total_activities
            else ""
        }
            </div>
            <div style="background: white; padding: 15px; border-radius: 5px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #2c3e50;">{
            probe_count
        }</div>
                <div style="color: #7f8c8d; font-size: 0.9em;">Validation Probes</div>
            </div>
        </div>
        <div style="margin-top: 15px; padding: 10px; background: white; border-radius: 5px;">
            <strong>Test State:</strong> <span class="{state_class}">{test_state}</span>
            <span style="margin-left: 20px;">
                <strong>Activities:</strong> {successful_activities}/{
            total_activities
        } succeeded
                <span style="margin-left: 20px;">
                <strong>Probes:</strong> {passed_probes}/{probe_count} passed
            </span>
        </div>
        {
            (
                f'<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 5px; border-left: 4px solid #ffc107;">'
                f"<strong>Note:</strong> Experiment was interrupted. Showing executed counts "
                f"({scenario_count}/{planned_scenario_count} scenarios, {total_activities}/{planned_activity_count} activities). "
                f"Grafana shows planned counts ({planned_scenario_count} scenarios, {planned_activity_count} activities)."
                f"</div>"
                if planned_scenario_count > scenario_count
                or planned_activity_count > total_activities
                else ""
            )
        }
    </div>
"""
        return html

    def _generate_scenario_summary(self, run: list[dict[str, Any]]) -> str:
        """
        Generate a summary of scenarios with success counts and percentages.
        """
        scenarios = self._group_activities_by_scenario(run)

        if not scenarios:
            return ""

        html = "<h3>Scenario Summary</h3><table><tr><th>Scenario</th><th>Total Activities</th><th>Successful</th><th>Success Rate</th></tr>"

        for scenario_name in sorted(scenarios.keys()):
            activities = scenarios[scenario_name]
            # Filter out the SCENARIO action itself for counting
            sub_activities = [
                a for a in activities if not a["name"].startswith("SCENARIO-")
            ]

            total = len(sub_activities)
            successful = sum(1 for a in sub_activities if a["status"] == "succeeded")
            success_rate = (successful / total * 100) if total > 0 else 0.0

            status_class = (
                "status-passed"
                if success_rate == 100.0
                else "status-failed"
                if success_rate < 50.0
                else ""
            )

            # Format scenario name (remove SCENARIO- prefix if present)
            display_name = (
                scenario_name.replace("SCENARIO-", "")
                if scenario_name.startswith("SCENARIO-")
                else scenario_name
            )

            html += f"""
            <tr>
                <td><strong>{display_name}</strong></td>
                <td>{total}</td>
                <td>{successful}</td>
                <td class="{status_class}">{success_rate:.1f}%</td>
            </tr>
"""

        html += "</table>"
        return html

    def _generate_tests_summary(self, run: list[dict[str, Any]]) -> str:
        """
        Generate a summary of all tests run for executive report.
        """
        scenarios = self._group_activities_by_scenario(run)

        if not scenarios:
            return ""

        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;"><h2>Summary of All Tests Run</h2>'

        for scenario_name in sorted(scenarios.keys()):
            activities = scenarios[scenario_name]
            # Filter out the SCENARIO action itself for counting
            sub_activities = [
                a for a in activities if not a["name"].startswith("SCENARIO-")
            ]

            total = len(sub_activities)
            successful = sum(1 for a in sub_activities if a["status"] == "succeeded")
            success_rate = (successful / total * 100) if total > 0 else 0.0

            # Format scenario name
            display_name = (
                scenario_name.replace("SCENARIO-", "")
                if scenario_name.startswith("SCENARIO-")
                else scenario_name
            )

            html += f"""
    <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 3px;">
        <strong>{display_name}:</strong> {successful}/{total} tests passed ({success_rate:.1f}%)
    </div>
"""

        html += "</div>"
        return html

    def _generate_test_category_section(
        self, category_name: str, tests_data: dict[str, dict[str, Any]]
    ) -> str:
        """
        Generate HTML section for a test category (End-to-End Tests, Application Tests, Infrastructure Components).
        """
        if not tests_data:
            return ""

        html = f"<h3>{category_name}</h3>"

        # Sort by resilience score (highest first)
        sorted_tests = sorted(
            tests_data.items(),
            key=lambda x: (
                (x[1]["successful"] / x[1]["total"] * 100) if x[1]["total"] > 0 else 0
            ),
            reverse=True,
        )

        for test_name, data in sorted_tests:
            total = data["total"]
            successful = data["successful"]
            failed = data["failed"]

            # Calculate resilience score
            if total > 0:
                resilience_score = (successful / total) * 100
            else:
                resilience_score = 0.0

            # Determine score class
            if resilience_score >= 80:
                score_class = "score-high"
                score_label = "High"
            elif resilience_score >= 50:
                score_class = "score-medium"
                score_label = "Medium"
            else:
                score_class = "score-low"
                score_label = "Low"

            # Get component type for infrastructure components
            component_type = data.get("component_type", "")
            type_display = (
                f' <span style="font-size: 0.8em; color: #7f8c8d;">({component_type})</span>'
                if component_type
                else ""
            )

            html += f"""
    <div class="service">
        <div class="service-header">
            <div class="service-name">{test_name}{type_display}</div>
            <div class="resilience-score {score_class}">
                {resilience_score:.1f}% ({score_label})
            </div>
        </div>

        <div class="metrics">
            <div class="metric-box">
                <div class="metric-label">Total Activities</div>
                <div class="metric-value">{total}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Successful</div>
                <div class="metric-value" style="color: #27ae60;">{successful}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Failed</div>
                <div class="metric-value" style="color: #e74c3c;">{failed}</div>
            </div>
        </div>

        <div class="activities-list">
            <strong>Activities:</strong>
"""

            for activity in data["activities"]:
                activity_class = (
                    "activity-success"
                    if activity["status"] == "succeeded"
                    else "activity-failed"
                )
                html += f"""
            <div class="activity {activity_class}">
                {activity["name"]} ({activity["type"]}) - {activity["status"]}
            </div>
"""

            html += """
        </div>
    </div>
"""

        return html

    def _generate_scenario_details(self, run: list[dict[str, Any]]) -> str:
        """
        Generate detailed activities grouped by SCENARIO.
        """
        scenarios = self._group_activities_by_scenario(run)

        if not scenarios:
            return ""

        html = '<div class="section"><h2>Detailed Activities by Scenario</h2>'

        for scenario_name in sorted(scenarios.keys()):
            activities = scenarios[scenario_name]

            # Format scenario name
            display_name = (
                scenario_name.replace("SCENARIO-", "")
                if scenario_name.startswith("SCENARIO-")
                else scenario_name
            )

            html += f"<h3>{display_name}</h3><table><tr><th>Type</th><th>Name</th><th>Status</th></tr>"

            for activity in activities:
                activity_name = activity["name"]
                activity_type = activity["type"]
                activity_status = activity["status"]

                # Extract provider information for better display
                activity_entry = activity.get("entry", {})
                activity_obj = activity_entry.get("activity", activity_entry)
                provider = activity_obj.get("provider", {})
                provider_module = provider.get("module", "")

                # Build a more descriptive name if available
                if activity_name == "unknown" and provider_module:
                    module_parts = provider_module.split(".")
                    if len(module_parts) > 1:
                        activity_name = f"{module_parts[-2]}.{module_parts[-1]}"

                status_class = (
                    "status-passed"
                    if activity_status == "succeeded"
                    else "status-failed"
                    if activity_status == "failed"
                    else ""
                )

                html += f"""
                <tr>
                    <td>{activity_type}</td>
                    <td>{activity_name}</td>
                    <td class="{status_class}">{activity_status}</td>
                </tr>
"""

            html += "</table>"

        html += "</div>"
        return html

    def _generate_test_category_section(
        self, category_name: str, tests_data: dict[str, dict[str, Any]]
    ) -> str:
        """
        Generate HTML section for a test category (End-to-End Tests, Application Tests, Infrastructure Components).
        """
        if not tests_data:
            return ""

        html = f"<h3>{category_name}</h3>"

        # Sort by resilience score (highest first)
        sorted_tests = sorted(
            tests_data.items(),
            key=lambda x: (
                (x[1]["successful"] / x[1]["total"] * 100) if x[1]["total"] > 0 else 0
            ),
            reverse=True,
        )

        for test_name, data in sorted_tests:
            total = data["total"]
            successful = data["successful"]
            failed = data["failed"]

            # Calculate resilience score
            if total > 0:
                resilience_score = (successful / total) * 100
            else:
                resilience_score = 0.0

            # Determine score class
            if resilience_score >= 80:
                score_class = "score-high"
                score_label = "High"
            elif resilience_score >= 50:
                score_class = "score-medium"
                score_label = "Medium"
            else:
                score_class = "score-low"
                score_label = "Low"

            # Get component type for infrastructure components
            component_type = data.get("component_type", "")
            type_display = (
                f' <span style="font-size: 0.8em; color: #7f8c8d;">({component_type})</span>'
                if component_type
                else ""
            )

            html += f"""
    <div class="service">
        <div class="service-header">
            <div class="service-name">{test_name}{type_display}</div>
            <div class="resilience-score {score_class}">
                {resilience_score:.1f}% ({score_label})
            </div>
        </div>

        <div class="metrics">
            <div class="metric-box">
                <div class="metric-label">Total Activities</div>
                <div class="metric-value">{total}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Successful</div>
                <div class="metric-value" style="color: #27ae60;">{successful}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Failed</div>
                <div class="metric-value" style="color: #e74c3c;">{failed}</div>
            </div>
        </div>

        <div class="activities-list">
            <strong>Activities:</strong>
"""

            for activity in data["activities"]:
                activity_class = (
                    "activity-success"
                    if activity["status"] == "succeeded"
                    else "activity-failed"
                )
                html += f"""
            <div class="activity {activity_class}">
                {activity["name"]} ({activity["type"]}) - {activity["status"]}
            </div>
"""

            html += """
        </div>
    </div>
"""

        return html
