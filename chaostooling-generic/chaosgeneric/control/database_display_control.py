"""
Database Display Control Module

Chaos Toolkit control that displays database steady-state and experiment overview data
as ASCII tables at the beginning and end of experiments.

Lifecycle hooks:
- before_experiment_control(): Display baseline/steady-state metrics table
- after_experiment_control(): Display experiment overview/results table
"""

import logging
from datetime import datetime
from typing import Any

from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger(__name__)


def before_experiment_display(context: dict[str, Any], **kwargs) -> None:
    """
    Display database steady-state baseline metrics as ASCII table before experiment starts.

    Shows:
    - Baseline collection timestamp
    - Steady-state metrics (mean, stdev, bounds)
    - System configuration

    Args:
        context: Chaos Toolkit context dict
        **kwargs: Additional arguments passed by Chaos Toolkit
    """
    logger.info("\n" + "=" * 100)
    logger.info("CHAOS EXPERIMENT: DATABASE STEADY-STATE BASELINE")
    logger.info("=" * 100)

    try:
        db_host = context.get("db_host", "localhost")
        db_port = context.get("db_port", 5434)

        db = ChaosDb(host=db_host, port=db_port)

        # Get all baseline metrics for all services
        try:
            result = db.session.execute("""
                SELECT
                    service_name,
                    metric_name,
                    mean,
                    stdev,
                    lower_bound_2sigma,
                    upper_bound_2sigma,
                    lower_bound_3sigma,
                    upper_bound_3sigma,
                    collection_timestamp
                FROM baseline_metrics
                ORDER BY service_name, metric_name
            """)

            baselines = result.fetchall()

            if baselines:
                # Group by service
                services = {}
                for row in baselines:
                    service = row[0]
                    if service not in services:
                        services[service] = []
                    services[service].append(row)

                # Display table for each service
                for service, metrics in services.items():
                    _display_baseline_table(service, metrics)
            else:
                logger.warning("No baseline metrics found in database")

        except Exception as db_error:
            logger.warning(f"Could not retrieve baseline from database: {db_error}")
            logger.info("Baseline data may not be available yet")

        logger.info("=" * 100 + "\n")

    except Exception as e:
        logger.warning(f"Error displaying baseline metrics: {e}")
        # Don't fail the experiment if display fails
        pass


def after_experiment_display(context: dict[str, Any], **kwargs) -> None:
    """
    Display experiment overview and results as ASCII table after experiment completes.

    Shows:
    - Experiment metadata (name, duration, timestamp)
    - Execution summary (probes passed/failed, actions executed)
    - Key findings
    - Anomalies detected
    - Database storage summary

    Args:
        context: Chaos Toolkit context dict
        **kwargs: Additional arguments passed by Chaos Toolkit
    """
    logger.info("\n" + "=" * 100)
    logger.info("CHAOS EXPERIMENT: RESULTS OVERVIEW")
    logger.info("=" * 100)

    try:
        db_host = context.get("db_host", "localhost")
        db_port = context.get("db_port", 5434)
        run_id = context.get("run_id", "unknown")

        db = ChaosDb(host=db_host, port=db_port)

        # Get experiment run details
        try:
            result = db.session.execute(
                """
                SELECT
                    run_id,
                    experiment_name,
                    start_timestamp,
                    end_timestamp,
                    status,
                    probes_passed,
                    probes_failed,
                    actions_executed,
                    rollback_status,
                    findings_summary
                FROM experiment_runs
                WHERE run_id = :run_id
                LIMIT 1
            """,
                {"run_id": run_id},
            )

            run_row = result.fetchone()

            if run_row:
                _display_experiment_overview_table(run_row)

                # Display metric snapshots summary
                _display_metric_snapshots_table(db, run_id)

            else:
                logger.info(f"No experiment run record found for {run_id}")

        except Exception as db_error:
            logger.warning(f"Could not retrieve experiment results: {db_error}")

        logger.info("=" * 100 + "\n")

    except Exception as e:
        logger.warning(f"Error displaying experiment results: {e}")
        # Don't fail the experiment if display fails
        pass


def _display_baseline_table(service_name: str, metrics: list) -> None:
    """Display baseline metrics as formatted ASCII table."""

    logger.info(f"\nService: {service_name}")
    logger.info(f"{'-' * 95}")

    # Header
    header = (
        f"{'Metric Name':<30} | "
        f"{'Mean':>10} | "
        f"{'StDev':>10} | "
        f"{'2σ Lower':>10} | "
        f"{'2σ Upper':>10} | "
        f"{'3σ Lower':>10} | "
        f"{'3σ Upper':>10}"
    )
    logger.info(header)
    logger.info(f"{'-' * 95}")

    # Rows
    for row in metrics:
        metric_name = row[1]
        mean = f"{float(row[2]):.2f}" if row[2] else "N/A"
        stdev = f"{float(row[3]):.2f}" if row[3] else "N/A"
        lower_2sigma = f"{float(row[4]):.2f}" if row[4] else "N/A"
        upper_2sigma = f"{float(row[5]):.2f}" if row[5] else "N/A"
        lower_3sigma = f"{float(row[6]):.2f}" if row[6] else "N/A"
        upper_3sigma = f"{float(row[7]):.2f}" if row[7] else "N/A"

        line = (
            f"{metric_name:<30} | "
            f"{mean:>10} | "
            f"{stdev:>10} | "
            f"{lower_2sigma:>10} | "
            f"{upper_2sigma:>10} | "
            f"{lower_3sigma:>10} | "
            f"{upper_3sigma:>10}"
        )
        logger.info(line)

    logger.info(f"{'-' * 95}")


def _display_experiment_overview_table(run_row: tuple) -> None:
    """Display experiment overview as formatted ASCII table."""

    run_id = run_row[0]
    exp_name = run_row[1]
    start_ts = run_row[2]
    end_ts = run_row[3]
    status = run_row[4]
    probes_passed = run_row[5] or 0
    probes_failed = run_row[6] or 0
    actions_executed = run_row[7] or 0
    rollback_status = run_row[8] or "N/A"
    findings = run_row[9] or "No findings"

    # Calculate duration
    try:
        if isinstance(start_ts, str):
            start_dt = datetime.fromisoformat(start_ts)
        else:
            start_dt = start_ts

        if isinstance(end_ts, str):
            end_dt = datetime.fromisoformat(end_ts)
        else:
            end_dt = end_ts

        duration = (end_dt - start_dt).total_seconds()
        duration_str = f"{int(duration)}s"
    except Exception:
        duration_str = "N/A"

    # Metadata section
    logger.info("\n📋 EXPERIMENT METADATA")
    logger.info(f"{'-' * 95}")
    logger.info(f"{'Run ID':<30}: {run_id}")
    logger.info(f"{'Experiment':<30}: {exp_name}")
    logger.info(f"{'Status':<30}: {status.upper()}")
    logger.info(f"{'Duration':<30}: {duration_str}")
    logger.info(f"{'Started':<30}: {start_ts}")
    logger.info(f"{'Ended':<30}: {end_ts}")
    logger.info(f"{'-' * 95}")

    # Execution summary section
    logger.info("\n📊 EXECUTION SUMMARY")
    logger.info(f"{'-' * 95}")
    summary_data = [
        ("Probes Passed", str(probes_passed), "✓"),
        ("Probes Failed", str(probes_failed), "✗" if probes_failed > 0 else "✓"),
        ("Actions Executed", str(actions_executed), "✓"),
        (
            "Rollback Status",
            rollback_status,
            "✓" if rollback_status.upper() == "SUCCESS" else "⚠",
        ),
    ]

    for metric, value, symbol in summary_data:
        logger.info(f"{symbol} {metric:<28}: {value:>10}")
    logger.info(f"{'-' * 95}")

    # Findings section
    logger.info("\n🔍 KEY FINDINGS")
    logger.info(f"{'-' * 95}")
    findings_list = (
        findings.split("\n") if isinstance(findings, str) else [str(findings)]
    )
    for finding in findings_list:
        if finding.strip():
            logger.info(f"  • {finding.strip()}")
    logger.info(f"{'-' * 95}")


def _display_metric_snapshots_table(db: ChaosDb, run_id: str) -> None:
    """Display metric snapshots summary from experiment execution."""

    try:
        result = db.session.execute(
            """
            SELECT
                snapshot_phase,
                COUNT(*) as metric_count,
                MIN(snapshot_timestamp) as first_snapshot,
                MAX(snapshot_timestamp) as last_snapshot
            FROM metric_snapshots
            WHERE run_id = :run_id
            GROUP BY snapshot_phase
            ORDER BY snapshot_phase
        """,
            {"run_id": run_id},
        )

        snapshots = result.fetchall()

        if snapshots:
            logger.info("\n📈 METRIC SNAPSHOTS COLLECTED")
            logger.info(f"{'-' * 95}")

            header = f"{'Phase':<20} | {'Metrics':<10} | {'First Snapshot':<30} | {'Last Snapshot':<30}"
            logger.info(header)
            logger.info(f"{'-' * 95}")

            for row in snapshots:
                phase = row[0]
                count = row[1]
                first = row[2] or "N/A"
                last = row[3] or "N/A"

                line = f"{phase:<20} | {count:<10} | {str(first):<30} | {str(last):<30}"
                logger.info(line)

            logger.info(f"{'-' * 95}")

    except Exception as e:
        logger.debug(f"Could not display metric snapshots: {e}")


# Control hook functions (called by Chaos Toolkit)
def start_database_display(context: dict[str, Any], **kwargs) -> None:
    """
    Chaos Toolkit before_experiment_control hook.
    Displays baseline/steady-state metrics.
    """
    before_experiment_display(context, **kwargs)


def stop_database_display(context: dict[str, Any], **kwargs) -> None:
    """
    Chaos Toolkit after_experiment_control hook.
    Displays experiment overview and results.
    """
    after_experiment_display(context, **kwargs)
