"""
MCP Baseline Control Module

Loads steady state baselines from database during experiment initialization.
Supports multiple discovery strategies (system, service, explicit metrics, labels).
Integrates with BaselineLoader to load and validate baselines before experiment.
Stores baseline-experiment mappings in PostgreSQL for audit trail and analysis.

This module implements Task 2.1 of the Baseline Metrics Integration.
"""

import logging
from typing import Any, Optional

from chaosgeneric.data.chaos_db import ChaosDb
from chaosgeneric.tools.baseline_loader import BaselineLoader, BaselineMetric

logger = logging.getLogger(__name__)


class MCPBaselineControl:
    """
    Control provider that loads baselines from database using BaselineLoader.

    Supports multiple discovery strategies:
    - By system: Load all metrics for a system/environment
    - By service: Load all metrics for a service
    - By explicit metrics: Load specific named metrics
    - By labels: Load metrics matching Grafana labels

    Validates baselines for freshness and quality, then creates
    baseline-experiment mappings in database for audit trail.
    """

    def __init__(self):
        self.loader: Optional[BaselineLoader] = None
        self.loaded_baselines: dict[str, BaselineMetric] = {}
        self.db: Optional[ChaosDb] = None
        self.experiment_id: Optional[int] = None

    def before_experiment_starts(self, context: dict[str, Any], **config):
        """
        Called before experiment starts. Load and validate baselines.

        Loads baselines from database using discovery method specified in config:
        - discovery_method: "system", "service", "explicit", or "labels"
        - discovery_params: Parameters for chosen discovery method
        - validation: Validation parameters (max_age_days, min_quality_score)

        Creates baseline_experiment_mapping entries for audit trail.
        Stores loaded_baselines in context for use by probes.

        Args:
            context: Chaos context dict (gets populated with loaded_baselines)
            config: Configuration dict with:
                - discovery_method: Type of baseline discovery ("system", "service", "explicit", "labels")
                - discovery_params: Dict of parameters for discovery method
                - validation: Dict with validation options:
                  - max_age_days: Maximum age in days (default: 30)
                  - min_quality_score: Minimum quality score 0-1 (default: 0.7)
                  - fail_on_invalid: Whether to fail if baselines invalid (default: True)
                - db_host: Database host (default: localhost)
                - db_port: Database port (default: 5434)
        """
        logger.info("=" * 80)
        logger.info("MCPBaselineControl: Phase 2.1 - Loading and validating baselines")
        logger.info("=" * 80)

        try:
            # Get experiment ID from context
            self.experiment_id = context.get("experiment_id")
            if not self.experiment_id:
                raise ValueError(
                    "experiment_id required in context for baseline mapping. "
                    "Ensure experiment is created before applying baseline control."
                )
            logger.info(f"Experiment ID: {self.experiment_id}")

            # Initialize database connection
            self.db = ChaosDb(
                host=config.get("db_host", "localhost"),
                port=config.get("db_port", 5434),
            )
            logger.info("✓ Connected to chaos_platform database")

            # Initialize baseline loader
            self.loader = BaselineLoader(db_client=self.db, logger=logger)
            logger.info("✓ Initialized BaselineLoader")

            # Get discovery configuration
            discovery_method = config.get("discovery_method", "system")
            discovery_params = config.get("discovery_params", {})

            logger.info(f"\nDiscovery Method: {discovery_method}")
            logger.info(f"Discovery Params: {discovery_params}")

            # Load baselines using specified discovery method
            self.loaded_baselines = self._load_baselines_by_method(
                discovery_method, discovery_params
            )

            if not self.loaded_baselines:
                logger.warning(
                    "⚠️  No baselines loaded - experiment may not have baseline checks"
                )
                context["loaded_baselines"] = {}
                context["baseline_config"] = config
                return

            logger.info(f"\n✓ Loaded {len(self.loaded_baselines)} baseline metrics")

            # Validate baselines
            validation_config = config.get("validation", {})
            self._validate_and_log_baselines(validation_config)

            # Create baseline-experiment mappings
            mapping_count = self._create_baseline_mappings()
            logger.info(f"✓ Created {mapping_count} baseline-experiment mappings")

            # Store baselines in context for probes to use
            context["loaded_baselines"] = self.loaded_baselines
            context["baseline_config"] = config

            logger.info("\n" + "=" * 80)
            logger.info("✓ Baseline loading complete")
            logger.info(f"  Baselines loaded: {len(self.loaded_baselines)}")
            logger.info(f"  Mappings created: {mapping_count}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Failed to load baselines: {str(e)}")
            raise

    def after_experiment_ends(
        self, context: dict[str, Any], state: dict[str, Any], **config
    ):
        """
        Called after experiment completes.

        Baseline results are already stored in baseline_experiment_mapping table
        from before_experiment_starts. Probes will have recorded actual measurements
        against these baselines.

        Args:
            context: Chaos context
            state: Final experiment state
            config: Configuration dict
        """
        logger.info("MCPBaselineControl: Experiment completed")
        logger.info("Baseline results stored in baseline_experiment_mapping table")

    def _load_baselines_by_method(
        self, discovery_method: str, discovery_params: dict[str, Any]
    ) -> dict[str, BaselineMetric]:
        """
        Load baselines using specified discovery method.

        Args:
            discovery_method: One of "system", "service", "explicit", "labels"
            discovery_params: Parameters for the discovery method

        Returns:
            Dict mapping metric_name -> BaselineMetric
        """
        logger.info(f"\nLoading baselines using '{discovery_method}' discovery...")

        if discovery_method == "system":
            system = discovery_params.get("system")
            if not system:
                raise ValueError(
                    "discovery_method='system' requires 'system' in discovery_params"
                )

            include_patterns = discovery_params.get("include_patterns")
            exclude_patterns = discovery_params.get("exclude_patterns")

            baselines = self.loader.load_by_system(
                system=system,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
            logger.info(f"  Method: By System ('{system}')")

        elif discovery_method == "service":
            service_name = discovery_params.get("service_name")
            if not service_name:
                raise ValueError(
                    "discovery_method='service' requires 'service_name' in discovery_params"
                )

            include_patterns = discovery_params.get("include_patterns")
            exclude_patterns = discovery_params.get("exclude_patterns")

            baselines = self.loader.load_by_service(
                service_name=service_name,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
            logger.info(f"  Method: By Service ('{service_name}')")

        elif discovery_method == "explicit":
            metric_names = discovery_params.get("metric_names")
            if not metric_names:
                raise ValueError(
                    "discovery_method='explicit' requires 'metric_names' in discovery_params"
                )

            service_name = discovery_params.get("service_name")
            require_all = discovery_params.get("require_all", False)

            baselines = self.loader.load_by_metrics(
                metric_names=metric_names,
                service_name=service_name,
                require_all=require_all,
            )
            logger.info(f"  Method: Explicit Metrics ({len(metric_names)} requested)")

        elif discovery_method == "labels":
            labels = discovery_params.get("labels")
            if not labels:
                raise ValueError(
                    "discovery_method='labels' requires 'labels' in discovery_params"
                )

            match_all = discovery_params.get("match_all", True)

            baselines = self.loader.load_by_labels(labels=labels, match_all=match_all)
            logger.info(f"  Method: By Labels ({labels})")

        else:
            raise ValueError(
                f"Unknown discovery_method: {discovery_method}. "
                f"Use 'system', 'service', 'explicit', or 'labels'"
            )

        return baselines

    def _validate_and_log_baselines(self, validation_config: dict[str, Any]) -> None:
        """
        Validate baselines and log results.

        Args:
            validation_config: Validation parameters
                - max_age_days: Maximum acceptable age
                - min_quality_score: Minimum quality score
                - fail_on_invalid: Whether to fail if invalid
        """
        max_age_days = validation_config.get("max_age_days", 30)
        min_quality_score = validation_config.get("min_quality_score", 0.7)
        fail_on_invalid = validation_config.get("fail_on_invalid", True)

        logger.info(f"\nValidating {len(self.loaded_baselines)} baselines...")
        logger.info(f"  Max age: {max_age_days} days")
        logger.info(f"  Min quality: {min_quality_score}")

        # Validate baselines
        validation_results = self.loader.validate_baselines(
            self.loaded_baselines,
            max_age_days=max_age_days,
            min_quality_score=min_quality_score,
        )

        # Log validation results
        valid_count = 0
        invalid_count = 0

        logger.info("\nValidation Results:")
        for metric_name, result in validation_results.items():
            is_valid = result["valid"]
            if is_valid:
                valid_count += 1
                logger.info(
                    f"  ✓ {metric_name}: VALID (age={result['age_days']}d, quality={result['quality_score']:.2f})"
                )
            else:
                invalid_count += 1
                reasons = result["reasons"]
                logger.warning(f"  ❌ {metric_name}: INVALID - {reasons}")

            # Log warnings even for valid baselines
            for warning in result.get("warnings", []):
                logger.warning(f"    ⚠️  {warning}")

        # Check if we should fail
        if invalid_count > 0 and fail_on_invalid:
            raise ValueError(
                f"Baseline validation failed: {invalid_count} invalid baselines. "
                f"Use fail_on_invalid=False to continue anyway."
            )

        logger.info(
            f"\n✓ Validation complete: {valid_count} valid, {invalid_count} invalid"
        )

    def _create_baseline_mappings(self) -> int:
        """
        Create baseline-experiment mapping entries in database.

        One mapping entry per loaded baseline, linking the baseline to this
        experiment for audit trail and later comparison.

        Returns:
            Number of mappings created
        """
        if not self.db or not self.experiment_id:
            logger.warning(
                "Cannot create mappings: db or experiment_id not initialized"
            )
            return 0

        logger.info("\nCreating baseline-experiment mappings...")

        mapping_count = 0
        for metric_name, baseline in self.loaded_baselines.items():
            try:
                # Insert mapping entry
                mapping_id = self.db.insert_baseline_experiment_mapping(
                    experiment_id=self.experiment_id,
                    metric_id=baseline.metric_id,
                    baseline_version_id=baseline.baseline_version_id,
                    mapping_type="threshold_check",
                    sigma_threshold=2.0,
                    critical_sigma=3.0,
                    enable_anomaly_detection=True,
                    anomaly_method="zscore",
                    discovery_method=discovery_method,
                )
                mapping_count += 1
                logger.debug(f"  ✓ Created mapping {mapping_id} for {metric_name}")
            except Exception as e:
                logger.error(
                    f"  ❌ Failed to create mapping for {metric_name}: {str(e)}"
                )
                # Continue with other metrics even if one fails

        return mapping_count

    def get_baseline(self) -> dict[str, BaselineMetric]:
        """
        Get loaded baseline data. Can be called by probes and actions.

        Returns:
            Dict mapping metric_name -> BaselineMetric instance
        """
        return self.loaded_baselines


# Module-level functions for chaos toolkit integration
def before_experiment_starts(context, **config):
    """Integration point for chaos toolkit."""
    control = MCPBaselineControl()
    control.before_experiment_starts(context, **config)
    return control


def after_experiment_ends(context, state, **config):
    """Integration point for chaos toolkit."""
    logger.info("MCP baseline control: Experiment cleanup")
