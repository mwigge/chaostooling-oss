"""
MCP Baseline Control Module

Loads steady state baselines from MCP observability server during experiment initialization.
Baselines are discovered dynamically from Prometheus, Tempo, and Loki observability stack.
Stores results in PostgreSQL database (not JSON files) for audit trail and compliance.
"""

import json
import logging
from typing import Dict, Any, Optional
from chaosgeneric.mcp_observability_server import ObservabilityClient
from chaosgeneric.steady_state_analyzer import create_steady_state_analyzer
from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger(__name__)


class MCPBaselineControl:
    """
    Control provider that loads steady state baselines from MCP observability server.
    Integrates with chaos experiment workflow to dynamically discover baseline metrics.
    Stores baselines in PostgreSQL database for audit trail and compliance.
    """

    def __init__(self):
        self.client: Optional[ObservabilityClient] = None
        self.analyzer = None
        self.baseline_data: Dict[str, Any] = {}
        self.db: Optional[ChaosDb] = None

    def before_experiment_starts(self, context, **config):
        """
        Called before experiment starts. Initialize MCP client and load baselines.
        Stores baselines in database for audit trail and later comparison.
        
        Args:
            context: Chaos context
            config: Configuration dict with:
                - prometheus_url: Prometheus endpoint
                - tempo_url: Tempo endpoint
                - loki_url: Loki endpoint
                - grafana_url: Grafana endpoint
                - grafana_api_token: Grafana API token
                - service_name: Service to analyze (e.g., 'postgres')
                - analysis_period_days: Historical period to analyze
                - baseline_file: Output file for baseline data (optional, for backward compatibility)
                - db_host: Database host (default: localhost)
                - db_port: Database port (default: 5434)
        """
        logger.info("MCPBaselineControl: Loading steady state baselines from observability stack")
        
        try:
            # Initialize database connection
            self.db = ChaosDb(
                host=config.get("db_host", "localhost"),
                port=config.get("db_port", 5434)
            )
            logger.info("✓ Connected to chaos_platform database")
            
            # Initialize MCP observability client
            self.client = ObservabilityClient(
                prometheus_url=config.get("prometheus_url", "http://prometheus:9090"),
                tempo_url=config.get("tempo_url", "http://tempo:3100"),
                loki_url=config.get("loki_url", "http://loki:3100"),
                grafana_url=config.get("grafana_url", "http://grafana:3000"),
                grafana_api_token=config.get("grafana_api_token", "")
            )
            
            # Create steady state analyzer
            self.analyzer = create_steady_state_analyzer(
                prometheus_url=config.get("prometheus_url", "http://prometheus:9090"),
                tempo_url=config.get("tempo_url", "http://tempo:3100"),
                loki_url=config.get("loki_url", "http://loki:3100"),
                analysis_period_days=config.get("analysis_period_days", 14)
            )
            
            # Run analysis to capture baseline
            logger.info(f"Running steady state analysis for {config.get('service_name', 'system')} "
                       f"over {config.get('analysis_period_days', 14)} days")
            analysis_results = self.analyzer.analyze()
            
            # Extract baseline metrics for the service
            service_name = config.get("service_name", "postgres")
            self.baseline_data = {
                "service_name": service_name,
                "analysis_timestamp": analysis_results.get("analysis_report", {}).get("timestamp"),
                "baseline_metrics": analysis_results.get("baseline_metrics", {}),
                "slo_targets": analysis_results.get("slo_targets", {}),
                "service_topology": analysis_results.get("service_topology", {}),
                "anomaly_thresholds": analysis_results.get("anomaly_thresholds", {}),
                "analysis_report": analysis_results.get("analysis_report", {})
            }
            
            # Save baseline to database (primary storage)
            self.db.save_baseline_metrics(service_name, self.baseline_data)
            self.db.save_slo_targets(service_name, self.baseline_data)
            
            # Also save to file for backward compatibility (optional)
            baseline_file = config.get("baseline_file")
            if baseline_file:
                self._save_baseline_to_file(baseline_file)
            
            logger.info(f"✓ Baselines stored in database and loaded from observability stack")
            logger.info(f"  Service: {service_name}")
            logger.info(f"  Metrics analyzed: {len(self.baseline_data.get('baseline_metrics', {}))}")
            logger.info(f"  SLOs defined: {len(self.baseline_data.get('slo_targets', {}))}")
            
        except Exception as e:
            logger.error(f"Failed to load baselines from MCP: {str(e)}")
            raise

    def after_experiment_ends(self, context, state, **config):
        """
        Called after experiment completes. Can be used for cleanup or logging.
        
        Args:
            context: Chaos context
            state: Final experiment state
            config: Configuration dict
        """
        logger.info("MCPBaselineControl: Experiment completed")
        logger.info(f"Baseline data available in context for comparison")

    def _save_baseline(self, filepath: str) -> None:
        """
        Save baseline data to JSON file for use in probes and result analysis.
        Also available in database as primary storage.
        
        Args:
            filepath: Path to save baseline JSON file
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.baseline_data, f, indent=2, default=str)
            logger.info(f"Baseline also saved to {filepath} (for backward compatibility)")
        except Exception as e:
            logger.warning(f"Failed to save baseline to file {filepath}: {str(e)}")
            # Don't raise - database save is primary, file is optional

    def _save_baseline_to_file(self, filepath: str) -> None:
        """Save baseline to JSON file (backward compatibility)."""
        self._save_baseline(filepath)

    def get_baseline(self) -> Dict[str, Any]:
        """
        Get loaded baseline data. Can be called by probes and actions.
        
        Returns:
            Dict with baseline_metrics, slo_targets, anomaly_thresholds, etc.
        """
        return self.baseline_data


# Module-level functions for chaos toolkit integration
def before_experiment_starts(context, **config):
    """Integration point for chaos toolkit."""
    control = MCPBaselineControl()
    control.before_experiment_starts(context, **config)
    return control


def after_experiment_ends(context, state, **config):
    """Integration point for chaos toolkit."""
    logger.info("MCP baseline control: Experiment cleanup")
