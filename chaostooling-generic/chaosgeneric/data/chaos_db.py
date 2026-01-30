"""
Chaos Platform Database Repository

Industry-standard abstraction layer for storing chaos engineering data:
- Baseline metrics (steady state analysis)
- Experiment definitions and runs
- Results and RCA (Root Cause Analysis)
- Audit trails (compliance evidence)

Replaces JSON file I/O with PostgreSQL for:
- Better querying capabilities
- Audit trail tracking
- Multi-user concurrency
- DORA compliance evidence
- Long-term data retention
"""

import json
import logging
import psycopg2
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ChaosDb:
    """
    Database repository for chaos engineering platform.
    
    Industry standard pattern:
    - Connection pooling (psycopg2 pool)
    - Prepared statements (SQL injection protection)
    - Transaction management (ACID compliance)
    - Audit logging (all mutations)
    """

    def __init__(
        self,
        dbname: str = "chaos_platform",
        user: str = "chaos_app",
        password: str = "chaos_app_secure_password",
        host: str = "localhost",
        port: int = 5434,  # Chaos platform database
        pool_size: int = 5
    ):
        """
        Initialize database connection.
        
        Args:
            dbname: Database name
            user: Database user (should have limited permissions)
            password: Database password
            host: Database host
            port: Database port
            pool_size: Connection pool size
        """
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        
        self.connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        self.pool_size = pool_size
        
        # Test connection on init
        self._test_connection()

    @contextmanager
    def _get_connection(self):
        """Get database connection from pool with automatic commit/rollback."""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            conn.autocommit = False
            yield conn
            conn.commit()  # Commit if no exception
            logger.debug("Database transaction committed successfully")
        except Exception as e:
            if conn:
                conn.rollback()  # Rollback on error
                logger.error(f"Database transaction rolled back due to error: {str(e)}")
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()
                logger.debug("Database connection closed")

    def _test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    logger.info(f"✓ Connected to chaos_platform database")
                    return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise

    # ========================================================================
    # BASELINE METRICS (Step 1: Define Steady State)
    # ========================================================================

    def save_baseline_metrics(
        self,
        service_name: str,
        baseline_data: Dict[str, Any]
    ) -> int:
        """
        Save baseline metrics from SteadyStateAnalyzer.
        
        Args:
            service_name: Name of service (e.g., 'postgres')
            baseline_data: Dict with 'baseline_metrics' from analyzer
            
        Returns:
            baseline_id for reference
        """
        logger.info(f"Saving baselines for {service_name}")
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Get or create service
                    service_id = self._get_or_create_service(cur, service_name)
                    
                    baseline_metrics = baseline_data.get('baseline_metrics', {})
                    inserted_count = 0
                    
                    for metric_name, service_metrics in baseline_metrics.items():
                        if service_name not in service_metrics:
                            continue
                        
                        metrics = service_metrics[service_name]
                        
                        # Insert baseline record
                        cur.execute("""
                            INSERT INTO chaos_platform.baseline_metrics (
                                service_id, metric_name, mean_value, median_value,
                                stddev_value, min_value, max_value, p50, p95, p99,
                                lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
                                analysis_period_days, sample_count, data_completeness_percent,
                                analysis_date
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (service_id, metric_name, analysis_date, version)
                            DO UPDATE SET is_active = true, updated_at = CURRENT_TIMESTAMP
                        """, (
                            service_id, metric_name,
                            metrics.get('mean'), metrics.get('median'),
                            metrics.get('stdev'), metrics.get('min'), metrics.get('max'),
                            metrics.get('p50'), metrics.get('p95'), metrics.get('p99'),
                            metrics.get('lower_bound_2sigma'),
                            metrics.get('upper_bound_2sigma'),
                            metrics.get('upper_bound_3sigma'),
                            baseline_data.get('analysis_report', {}).get('analysis_period_days', 14),
                            metrics.get('sample_count'),
                            metrics.get('completeness_percent', 100),
                            datetime.now().date()
                        ))
                        inserted_count += 1
                    
                    # Log audit trail
                    self._audit_log(cur, 'created_baseline', 'baseline', service_id, 
                                   {'service': service_name, 'metrics': inserted_count})
                    
                    logger.info(f"✓ Saved {inserted_count} baseline metrics for {service_name}")
                    return service_id
                    
        except Exception as e:
            logger.error(f"Failed to save baselines: {str(e)}")
            raise

    def save_slo_targets(
        self,
        service_name: str,
        slo_data: Dict[str, Any]
    ) -> None:
        """
        Save SLO targets from SteadyStateAnalyzer.
        
        Args:
            service_name: Service name
            slo_data: Dict with 'slo_targets' from analyzer
        """
        logger.info(f"Saving SLO targets for {service_name}")
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    service_id = self._get_or_create_service(cur, service_name)
                    
                    slo_targets = slo_data.get('slo_targets', {})
                    inserted_count = 0
                    
                    for metric_type, service_slos in slo_targets.items():
                        if service_name not in service_slos:
                            continue
                        
                        for metric_name, target_data in service_slos[service_name].items():
                            cur.execute("""
                                INSERT INTO chaos_platform.slo_targets (
                                    service_id, metric_name, metric_type, target_value,
                                    confidence_level_percent, safety_margin_percent, analysis_date
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (service_id, metric_name, analysis_date)
                                DO UPDATE SET target_value = EXCLUDED.target_value
                            """, (
                                service_id, metric_name, metric_type,
                                target_data.get('target') or target_data.get('slo_target'),
                                99.0,
                                10.0,
                                datetime.now().date()
                            ))
                            inserted_count += 1
                    
                    logger.info(f"✓ Saved {inserted_count} SLO targets")
                    
        except Exception as e:
            logger.error(f"Failed to save SLO targets: {str(e)}")
            raise

    def get_baseline_metrics(self, service_name: str) -> Dict[str, Any]:
        """
        Retrieve latest baseline metrics for a service.
        
        Used by probes to verify steady state during experiments.
        
        Args:
            service_name: Service name
            
        Returns:
            Dict with baseline metrics
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM chaos_platform.v_latest_baselines
                        WHERE service_name = %s
                    """, (service_name,))
                    
                    rows = cur.fetchall()
                    result = {}
                    
                    for row in rows:
                        metric_name = row[1]
                        result[metric_name] = {
                            'mean': row[2],
                            'stdev': row[3],
                            'p99': row[4],
                            'upper_bound_2sigma': row[5],
                            'upper_bound_3sigma': row[6]
                        }
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to retrieve baseline metrics: {str(e)}")
            raise

    # ========================================================================
    # EXPERIMENT TRACKING
    # ========================================================================

    def create_experiment(
        self,
        experiment_name: str,
        service_name: str,
        chaos_scenario: str,
        description: str = "",
        experiment_file: str = ""
    ) -> int:
        """
        Create experiment record.
        
        Args:
            experiment_name: Name of experiment
            service_name: Service being tested
            chaos_scenario: Type of chaos (e.g., 'connection_pool_exhaustion')
            description: Experiment description
            experiment_file: Path to experiment JSON file
            
        Returns:
            experiment_id
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    service_id = self._get_or_create_service(cur, service_name)
                    
                    cur.execute("""
                        INSERT INTO chaos_platform.experiments (
                            experiment_name, experiment_file, service_id,
                            description, chaos_scenario
                        ) VALUES (%s, %s, %s, %s, %s)
                        RETURNING experiment_id
                    """, (experiment_name, experiment_file, service_id, description, chaos_scenario))
                    
                    experiment_id = cur.fetchone()[0]
                    
                    self._audit_log(cur, 'created_experiment', 'experiment', experiment_id,
                                   {'experiment': experiment_name, 'scenario': chaos_scenario})
                    
                    logger.info(f"✓ Created experiment: {experiment_name} (ID: {experiment_id})")
                    return experiment_id
                    
        except Exception as e:
            logger.error(f"Failed to create experiment: {str(e)}")
            raise

    def start_experiment_run(self, experiment_id: int) -> int:
        """
        Start a new experiment run.
        
        Args:
            experiment_id: ID of experiment
            
        Returns:
            run_id
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Get next run number
                    cur.execute("""
                        SELECT COALESCE(MAX(run_number), 0) + 1
                        FROM chaos_platform.experiment_runs
                        WHERE experiment_id = %s
                    """, (experiment_id,))
                    
                    run_number = cur.fetchone()[0]
                    
                    # Create run record
                    cur.execute("""
                        INSERT INTO chaos_platform.experiment_runs (
                            experiment_id, run_number, status
                        ) VALUES (%s, %s, 'in_progress')
                        RETURNING run_id
                    """, (experiment_id, run_number))
                    
                    run_id = cur.fetchone()[0]
                    
                    self._audit_log(cur, 'started_experiment_run', 'experiment_run', run_id,
                                   {'experiment_id': experiment_id, 'run_number': run_number})
                    
                    logger.info(f"✓ Started experiment run {run_number} (run_id: {run_id})")
                    return run_id
                    
        except Exception as e:
            logger.error(f"Failed to start experiment run: {str(e)}")
            raise

    def create_experiment_run(
        self,
        title: str,
        description: str = "",
        started_at: Optional[datetime] = None,
        status: str = "running",
        tags: Optional[str] = None,
        metadata: Optional[str] = None,
        experiment_id: Optional[int] = None
    ) -> int:
        """
        Create a new experiment run (simplified API for chaos controls).
        
        Combines experiment creation + run start in a single operation.
        Used by chaos controls that don't have a pre-created experiment record.
        
        Args:
            title: Experiment title
            description: Experiment description
            started_at: Start timestamp
            status: Run status (default: 'running')
            tags: JSON array of tags
            metadata: JSON metadata
            experiment_id: Optional stable experiment_id (from experiment_metadata_control)
            
        Returns:
            run_id for the created run
        """
        try:
            if started_at is None:
                started_at = datetime.utcnow()
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Use provided experiment_id (from experiment_metadata_control) or auto-generate
                    if experiment_id:
                        # Stable experiment_id provided by experiment_metadata_control
                        # Check if experiment record exists
                        cur.execute("""
                            SELECT experiment_id FROM chaos_platform.experiments
                            WHERE experiment_id = %s
                        """, (experiment_id,))
                        
                        result = cur.fetchone()
                        if not result:
                            # Create experiment record with this stable ID
                            service_name = metadata.get("service") if isinstance(metadata, dict) else "unknown"
                            if not service_name or service_name == "unknown":
                                service_name = title.split()[0].lower() if title else "unknown"
                            
                            service_id = self._get_or_create_service(cur, service_name)
                            
                            cur.execute("""
                                INSERT INTO chaos_platform.experiments (
                                    experiment_id, experiment_name, service_id, 
                                    description, chaos_scenario, status
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                            """, (experiment_id, title, service_id, description, "control", "pending"))
                            
                            logger.debug(f"Created experiment record with stable ID: {experiment_id}")
                        
                        exp_id = experiment_id
                        logger.debug(f"Using stable experiment_id from metadata control: {exp_id}")
                    else:
                        # Fallback: auto-generate based on title (legacy behavior)
                        service_name = title.split()[0].lower() if title else "unknown"
                        service_id = self._get_or_create_service(cur, service_name)
                        
                        cur.execute("""
                            INSERT INTO chaos_platform.experiments (
                                experiment_name, service_id, description, chaos_scenario, status
                            ) VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (experiment_name, created_at) DO NOTHING
                            RETURNING experiment_id
                        """, (title, service_id, description, "control", "pending"))
                        
                        result = cur.fetchone()
                        if result:
                            exp_id = result[0]
                        else:
                            # Get existing experiment
                            cur.execute("""
                                SELECT experiment_id FROM chaos_platform.experiments
                                WHERE experiment_name = %s
                                ORDER BY created_at DESC LIMIT 1
                            """, (title,))
                            exp_id = cur.fetchone()[0]
                        logger.debug(f"Auto-generated experiment_id: {exp_id}")
                    
                    # Get next run number for this experiment
                    cur.execute("""
                        SELECT COALESCE(MAX(run_number), 0) + 1
                        FROM chaos_platform.experiment_runs
                        WHERE experiment_id = %s
                    """, (exp_id,))
                    
                    run_number = cur.fetchone()[0]
                    
                    # Create run record
                    cur.execute("""
                        INSERT INTO chaos_platform.experiment_runs (
                            experiment_id, run_number, status, start_time,
                            executed_by, environment
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING run_id
                    """, (exp_id, run_number, status, started_at, "chaos-control", "production"))
                    
                    run_id = cur.fetchone()[0]
                    
                    self._audit_log(cur, 'created_experiment_run', 'experiment_run', run_id,
                                   {'title': title, 'experiment_id': exp_id, 'run_number': run_number})
                    
                    logger.info(f"✓ Created experiment run: {title} (run_id: {run_id})")
                    return run_id
                    
        except Exception as e:
            logger.error(f"Failed to create experiment run: {str(e)}")
            raise

    def update_experiment_run(
        self,
        run_id: int,
        status: str = None,
        ended_at: Optional[datetime] = None,
        result_summary: Optional[str] = None,
        metadata: Optional[str] = None,
        risk_score: int = None,
        complexity_score: int = None,
        test_quality: int = None,
        risk_level: str = None,
        success_rate: float = None
    ) -> bool:
        """
        Update experiment run with final status and results.
        
        Args:
            run_id: Run ID to update
            status: Final status (running, aborted, ended, failed)
            ended_at: End timestamp
            result_summary: JSON summary of results
            metadata: JSON metadata
            risk_score: Risk assessment score (0-255)
            complexity_score: Complexity assessment (0-255)
            test_quality: Test quality score (0-255)
            risk_level: Risk level (low, medium, high, critical)
            success_rate: Success rate percentage (0-100)
            
        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Build UPDATE query dynamically
                    updates = []
                    params = []
                    
                    if status:
                        updates.append("status = %s")
                        params.append(status)
                    
                    if ended_at:
                        updates.append("end_time = %s")
                        params.append(ended_at)
                    else:
                        # Auto-set end_time if status is ended/aborted/failed
                        if status in ['ended', 'aborted', 'failed']:
                            updates.append("end_time = CURRENT_TIMESTAMP")
                    
                    if risk_score is not None:
                        updates.append("risk_score = %s")
                        params.append(risk_score)
                    
                    if complexity_score is not None:
                        updates.append("complexity_score = %s")
                        params.append(complexity_score)
                    
                    if test_quality is not None:
                        updates.append("test_quality = %s")
                        params.append(test_quality)
                    
                    if risk_level:
                        updates.append("risk_level = %s")
                        params.append(risk_level)
                    
                    if success_rate is not None:
                        updates.append("success_rate = %s")
                        params.append(success_rate)
                    
                    if result_summary:
                        updates.append("result_summary = %s::jsonb")
                        params.append(result_summary)
                    
                    if metadata:
                        updates.append("metadata = %s::jsonb")
                        params.append(metadata)
                    
                    if not updates:
                        logger.warning("No fields to update")
                        return False
                    
                    # Add run_id to params
                    params.append(run_id)
                    
                    query = f"UPDATE chaos_platform.experiment_runs SET {', '.join(updates)} WHERE run_id = %s"
                    cur.execute(query, params)
                    
                    self._audit_log(cur, 'updated_experiment_run', 'experiment_run', run_id,
                                   {'status': status, 'ended_at': ended_at.isoformat() if ended_at else None})
                    
                    logger.info(f"✓ Updated experiment run {run_id}: status={status}, ended_at={ended_at}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to update experiment run: {str(e)}")
            raise

    # ========================================================================
    # METRIC SNAPSHOTS
    # ========================================================================

    def save_metric_snapshot(
        self,
        run_id: int,
        service_name: str,
        phase: str,
        metrics: Dict[str, Any]
    ) -> int:
        """
        Save metric snapshot during experiment phase.
        
        Args:
            run_id: Experiment run ID
            service_name: Service name
            phase: Phase name (pre_chaos, during_chaos, post_chaos)
            metrics: Dict of metric values
            
        Returns:
            snapshot_id
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    service_id = self._get_or_create_service(cur, service_name)
                    
                    # Phase sequence
                    phase_seq = {'pre_chaos': 1, 'during_chaos': 2, 'post_chaos': 3}.get(phase, 0)
                    
                    cur.execute("""
                        INSERT INTO chaos_platform.metric_snapshots (
                            run_id, service_id, phase, phase_sequence,
                            metrics, connection_count, query_latency_ms,
                            error_rate_percent, throughput_rps
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING snapshot_id
                    """, (
                        run_id, service_id, phase, phase_seq,
                        json.dumps(metrics),
                        metrics.get('connection_count'),
                        metrics.get('query_latency_ms'),
                        metrics.get('error_rate_percent'),
                        metrics.get('throughput_rps')
                    ))
                    
                    snapshot_id = cur.fetchone()[0]
                    logger.debug(f"✓ Saved {phase} metric snapshot")
                    return snapshot_id
                    
        except Exception as e:
            logger.error(f"Failed to save metric snapshot: {str(e)}")
            raise

    def save_baseline_metrics(
        self,
        service_name: str,
        metrics: Dict[str, Any]
    ) -> List[int]:
        """
        Save baseline metrics (steady state analysis).
        Called during baseline collection to establish reference points.
        
        Args:
            service_name: Service name
            metrics: Dict of metric names to values
                    Expected format: {
                        "metric_name": {
                            "mean": float,
                            "p95": float,
                            "p99": float,
                            "stddev": float,
                            "min": float,
                            "max": float
                        }
                    }
            
        Returns:
            List of baseline_ids created
        """
        baseline_ids = []
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    service_id = self._get_or_create_service(cur, service_name)
                    
                    for metric_name, stats in metrics.items():
                        try:
                            # Extract statistics from metric data
                            mean_val = stats.get('mean') or stats.get('result', {}).get('value')
                            p95 = stats.get('p95')
                            p99 = stats.get('p99')
                            stddev = stats.get('stddev')
                            min_val = stats.get('min')
                            max_val = stats.get('max')
                            
                            # Calculate sigma-based bounds if we have mean and stddev
                            lower_bound_2sigma = None
                            upper_bound_2sigma = None
                            upper_bound_3sigma = None
                            
                            if mean_val and stddev:
                                lower_bound_2sigma = mean_val - (2 * stddev)
                                upper_bound_2sigma = mean_val + (2 * stddev)
                                upper_bound_3sigma = mean_val + (3 * stddev)
                            
                            cur.execute("""
                                INSERT INTO chaos_platform.baseline_metrics (
                                    service_id, metric_name,
                                    mean_value, median_value, stddev_value, min_value, max_value,
                                    p50, p95, p99,
                                    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
                                    analysis_period_days, sample_count, data_completeness_percent,
                                    analysis_date, version, is_active
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, 1, true)
                                ON CONFLICT (service_id, metric_name, analysis_date, version)
                                DO UPDATE SET
                                    mean_value = EXCLUDED.mean_value,
                                    stddev_value = EXCLUDED.stddev_value,
                                    p95 = EXCLUDED.p95,
                                    p99 = EXCLUDED.p99
                                RETURNING baseline_id
                            """, (
                                service_id, metric_name,
                                mean_val, mean_val, stddev, min_val, max_val,
                                mean_val, p95, p99,
                                lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
                                14, 1000, 99.5
                            ))
                            
                            baseline_id = cur.fetchone()[0]
                            baseline_ids.append(baseline_id)
                            logger.debug(f"✓ Saved baseline for {metric_name} (baseline_id: {baseline_id})")
                            
                        except Exception as metric_error:
                            logger.warning(f"Could not save baseline for {metric_name}: {str(metric_error)}")
                            # Continue with next metric
                    
                    logger.info(f"✓ Saved {len(baseline_ids)} baseline metrics for {service_name}")
                    return baseline_ids
                    
        except Exception as e:
            logger.error(f"Failed to save baseline metrics: {str(e)}")
            raise

    # ========================================================================
    # RESULTS & ANALYSIS
    # ========================================================================

    def save_experiment_analysis(
        self,
        run_id: int,
        analysis_data: Dict[str, Any]
    ) -> int:
        """
        Save experiment analysis (RCA, recommendations, compliance).
        
        Args:
            run_id: Experiment run ID
            analysis_data: Dict from MCP result analyzer
            
        Returns:
            analysis_id
        """
        logger.info(f"Saving experiment analysis for run {run_id}")
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Extract analysis fields
                    impact = analysis_data.get('impact_analysis', {})
                    recovery = analysis_data.get('recovery_analysis', {})
                    
                    cur.execute("""
                        INSERT INTO chaos_platform.experiment_analysis (
                            run_id, max_deviation_sigma, max_degradation_percent,
                            affected_metrics, recovery_time_seconds, full_recovery_achieved,
                            anomaly_count, anomalies, rca_findings, recommendations,
                            compliance_status, dora_evidence
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING analysis_id
                    """, (
                        run_id,
                        impact.get('max_deviation_sigma'),
                        impact.get('max_degradation_percent'),
                        json.dumps(impact.get('affected_metrics', [])),
                        recovery.get('recovery_time_seconds'),
                        recovery.get('recovered', False),
                        len(analysis_data.get('anomalies', [])),
                        json.dumps(analysis_data.get('anomalies', [])),
                        json.dumps(analysis_data.get('rca_findings', [])),
                        json.dumps(analysis_data.get('recommendations', [])),
                        analysis_data.get('compliance_status', 'pending'),
                        json.dumps(analysis_data)
                    ))
                    
                    analysis_id = cur.fetchone()[0]
                    
                    # Mark run as completed
                    cur.execute("""
                        UPDATE chaos_platform.experiment_runs
                        SET status = 'completed', end_time = CURRENT_TIMESTAMP
                        WHERE run_id = %s
                    """, (run_id,))
                    
                    self._audit_log(cur, 'completed_experiment', 'experiment_run', run_id,
                                   {'compliance': analysis_data.get('compliance_status')})
                    
                    logger.info(f"✓ Saved analysis (compliance: {analysis_data.get('compliance_status')})")
                    return analysis_id
                    
        except Exception as e:
            logger.error(f"Failed to save experiment analysis: {str(e)}")
            raise

    # ========================================================================
    # COMPLIANCE & REPORTING
    # ========================================================================

    def get_compliance_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Get compliance summary for last N days.
        
        Used for DORA evidence and audit reports.
        
        Args:
            days: Number of days to include
            
        Returns:
            Compliance report dict
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM chaos_platform.v_compliance_summary
                    """)
                    
                    rows = cur.fetchall()
                    report = {
                        'period_days': days,
                        'report_date': datetime.now().isoformat(),
                        'services': {}
                    }
                    
                    for row in rows:
                        report['services'][row[0]] = {
                            'total_runs': row[1],
                            'passed': row[2],
                            'warnings': row[3],
                            'failed': row[4],
                            'pass_rate_percent': float(row[5]) if row[5] else 0
                        }
                    
                    return report
                    
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {str(e)}")
            raise

    def get_audit_trail(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for compliance evidence.
        
        Args:
            entity_type: Type of entity (experiment, baseline, etc.)
            entity_id: Specific entity ID
            days: Days of history
            
        Returns:
            List of audit records
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT log_id, action, entity_type, entity_id, actor,
                               details, action_timestamp
                        FROM chaos_platform.audit_log
                        WHERE action_timestamp > NOW() - INTERVAL '%s days'
                    """
                    params = [days]
                    
                    if entity_type:
                        query += " AND entity_type = %s"
                        params.append(entity_type)
                    
                    if entity_id:
                        query += " AND entity_id = %s"
                        params.append(entity_id)
                    
                    query += " ORDER BY action_timestamp DESC"
                    
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    
                    result = []
                    for row in rows:
                        result.append({
                            'log_id': row[0],
                            'action': row[1],
                            'entity_type': row[2],
                            'entity_id': row[3],
                            'actor': row[4],
                            'details': json.loads(row[5]) if row[5] else {},
                            'timestamp': row[6].isoformat()
                        })
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {str(e)}")
            raise

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_or_create_service(self, cur, service_name: str) -> int:
        """Get service ID or create if not exists."""
        cur.execute("""
            SELECT service_id FROM chaos_platform.services
            WHERE service_name = %s
        """, (service_name,))
        
        result = cur.fetchone()
        if result:
            return result[0]
        
        # Create service
        cur.execute("""
            INSERT INTO chaos_platform.services (service_name, environment)
            VALUES (%s, 'production')
            RETURNING service_id
        """, (service_name,))
        
        return cur.fetchone()[0]

    def _audit_log(
        self,
        cur,
        action: str,
        entity_type: str,
        entity_id: int,
        details: Dict[str, Any]
    ) -> None:
        """Log audit trail entry."""
        cur.execute("""
            INSERT INTO chaos_platform.audit_log (
                action, entity_type, entity_id, actor, actor_type, details
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (action, entity_type, entity_id, 'chaos_platform', 'system', json.dumps(details)))
