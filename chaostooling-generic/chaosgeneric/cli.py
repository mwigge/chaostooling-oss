#!/usr/bin/env python
"""
CLI for Observability MCP Server and Steady State Analysis

Commands:
  mcp-server      - Start the MCP server (for Claude integration)
  analyze         - Run steady state analysis on observability data
  baseline        - Generate baseline metrics file
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import click

from chaosgeneric.mcp_observability_server import (
    InitializationOptions,
    create_server,
    stdio_server,
)
from chaosgeneric.steady_state_analyzer import create_steady_state_analyzer

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@click.group()
@click.version_option(version="1.0.0", prog_name="chaos-observability")
def cli():
    """Chaos Engineering Observability Tools"""
    pass


@cli.command()
@click.option(
    "--prometheus-url",
    default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
    help="Prometheus server URL",
)
@click.option(
    "--tempo-url",
    default=os.getenv("TEMPO_URL", "http://localhost:3100"),
    help="Tempo server URL",
)
@click.option(
    "--loki-url",
    default=os.getenv("LOKI_URL", "http://localhost:3100"),
    help="Loki server URL",
)
@click.option(
    "--grafana-url",
    default=os.getenv("GRAFANA_URL", "http://localhost:3000"),
    help="Grafana server URL",
)
@click.option(
    "--grafana-token",
    default=os.getenv("GRAFANA_API_TOKEN", ""),
    help="Grafana API token",
)
def mcp_server(
    prometheus_url: str,
    tempo_url: str,
    loki_url: str,
    grafana_url: str,
    grafana_token: str,
):
    """Start MCP server for observability stack integration"""

    # Set environment variables
    os.environ["PROMETHEUS_URL"] = prometheus_url
    os.environ["TEMPO_URL"] = tempo_url
    os.environ["LOKI_URL"] = loki_url
    os.environ["GRAFANA_URL"] = grafana_url
    os.environ["GRAFANA_API_TOKEN"] = grafana_token

    click.echo("Starting Observability MCP Server...")
    click.echo(f"  Prometheus: {prometheus_url}")
    click.echo(f"  Tempo: {tempo_url}")
    click.echo(f"  Loki: {loki_url}")
    click.echo(f"  Grafana: {grafana_url}")
    click.echo()
    click.echo("MCP Server ready. Waiting for connections...")

    async def run_server():
        server = create_server()
        async with stdio_server(server) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="observability-mcp",
                    server_version="1.0.0",
                ),
            )

    asyncio.run(run_server())


@cli.command()
@click.option(
    "--prometheus-url",
    default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
    help="Prometheus server URL",
)
@click.option(
    "--tempo-url",
    default=os.getenv("TEMPO_URL", "http://localhost:3100"),
    help="Tempo server URL",
)
@click.option(
    "--loki-url",
    default=os.getenv("LOKI_URL", "http://localhost:3100"),
    help="Loki server URL",
)
@click.option(
    "--period-days",
    default=14,
    help="Analysis period in days",
    type=int,
)
@click.option(
    "--output-dir",
    default="./chaos-analysis",
    help="Output directory for analysis results",
)
def analyze(
    prometheus_url: str,
    tempo_url: str,
    loki_url: str,
    period_days: int,
    output_dir: str,
):
    """Run steady state analysis on observability data"""

    click.echo("Starting Steady State Analysis...")
    click.echo(f"  Period: {period_days} days")
    click.echo(f"  Output: {output_dir}")
    click.echo()

    try:
        # Create analyzer
        analyzer = create_steady_state_analyzer(
            prometheus_url=prometheus_url,
            tempo_url=tempo_url,
            loki_url=loki_url,
            analysis_period_days=period_days,
        )

        # Run analysis
        with click.progressbar(length=4, label="Analyzing") as bar:
            bar.update(1)
            results = analyzer.analyze()
            bar.update(3)

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save results
        files_saved = []

        # Save baseline metrics
        baseline_file = output_path / "baseline_metrics.json"
        with open(baseline_file, "w") as f:
            json.dump(results["baseline_metrics"], f, indent=2)
        files_saved.append(str(baseline_file))
        bar.update(1)

        # Save SLOs
        slo_file = output_path / "slo_targets.json"
        with open(slo_file, "w") as f:
            json.dump(results["slo_targets"], f, indent=2)
        files_saved.append(str(slo_file))

        # Save topology
        topology_file = output_path / "service_topology.json"
        with open(topology_file, "w") as f:
            json.dump(results["service_topology"], f, indent=2)
        files_saved.append(str(topology_file))

        # Save thresholds
        threshold_file = output_path / "anomaly_thresholds.json"
        with open(threshold_file, "w") as f:
            json.dump(results["anomaly_thresholds"], f, indent=2)
        files_saved.append(str(threshold_file))

        # Save report
        report_file = output_path / "analysis_report.json"
        with open(report_file, "w") as f:
            json.dump(results["analysis_report"], f, indent=2)
        files_saved.append(str(report_file))

        bar.update(1)

        # Display results
        click.echo()
        click.echo("✓ Analysis Complete!")
        click.echo()
        click.echo("Results Summary:")
        click.echo(
            f"  Services analyzed: "
            f"{results['analysis_report']['summary']['services_analyzed']}"
        )
        click.echo(
            f"  Critical paths: "
            f"{results['analysis_report']['summary']['critical_paths']}"
        )
        click.echo(f"  SPOFs: {results['analysis_report']['summary']['spofs']}")
        click.echo()
        click.echo("Key Findings:")
        for finding in results["analysis_report"]["key_findings"]:
            click.echo(f"  • {finding}")
        click.echo()
        click.echo("Recommendations:")
        for rec in results["analysis_report"]["recommendations"]:
            click.echo(f"  • {rec}")
        click.echo()
        click.echo("Files saved:")
        for file in files_saved:
            click.echo(f"  ✓ {file}")

    except Exception as e:
        click.echo(f"✗ Analysis failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--prometheus-url",
    default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
    help="Prometheus server URL",
)
@click.option(
    "--output-file",
    default="baseline.json",
    help="Output file for baseline metrics",
)
def baseline(prometheus_url: str, output_file: str):
    """Generate baseline metrics file"""

    click.echo("Generating baseline metrics...")

    try:
        analyzer = create_steady_state_analyzer(
            prometheus_url=prometheus_url,
            analysis_period_days=14,
        )

        metrics = analyzer._collect_metrics()
        baselines = analyzer._calculate_baselines(metrics)

        with open(output_file, "w") as f:
            json.dump(baselines, f, indent=2)

        click.echo(f"✓ Baseline saved to {output_file}")

    except Exception as e:
        click.echo(f"✗ Failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
