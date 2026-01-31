"""
Experiment index for centralized tracking of all experiment runs.

Provides a queryable index of experiment runs with their reports and dashboards.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chaostooling_reporting.experiment_index")


class ExperimentIndex:
    """Central index of all experiment runs with reports and dashboards."""

    def __init__(self, storage_path: str = "./reports"):
        """
        Initialize experiment index.

        Args:
            storage_path: Directory to store the index file
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_path / "experiment_index.json"
        self._index = self._load_index()
        logger.info(f"ExperimentIndex initialized: {self.index_file}")

    def _load_index(self) -> dict[str, Any]:
        """Load index from file or create new one."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load index, creating new: {e}")

        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "experiments": {},
        }

    def _save_index(self) -> None:
        """Save index to file."""
        self._index["updated"] = datetime.now().isoformat()
        try:
            with open(self.index_file, "w") as f:
                json.dump(self._index, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def register_experiment(
        self,
        experiment_id: str,
        title: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        report_paths: Optional[dict[str, str]] = None,
        dashboard_uid: Optional[str] = None,
        dashboard_url: Optional[str] = None,
        systems: Optional[list[str]] = None,
        risk_level: Optional[str] = None,
        complexity_score: Optional[int] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Register a completed experiment in the index.

        Args:
            experiment_id: Unique experiment identifier
            title: Experiment title
            status: Final status (completed, failed, aborted)
            start_time: Experiment start timestamp
            end_time: Experiment end timestamp
            report_paths: Dictionary mapping report types to file paths
            dashboard_uid: Grafana dashboard UID
            dashboard_url: Grafana dashboard URL
            systems: List of systems affected
            risk_level: Risk level (low, medium, high, critical)
            complexity_score: Complexity score (1-5)
            tags: Additional tags for filtering
            metadata: Any additional metadata
        """
        entry = {
            "experiment_id": experiment_id,
            "title": title,
            "status": status,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "duration_seconds": (
                (end_time - start_time).total_seconds()
                if start_time and end_time
                else None
            ),
            "report_paths": report_paths or {},
            "dashboard_uid": dashboard_uid,
            "dashboard_url": dashboard_url,
            "systems": systems or [],
            "risk_level": risk_level,
            "complexity_score": complexity_score,
            "tags": tags or [],
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
        }

        self._index["experiments"][experiment_id] = entry
        self._save_index()
        logger.info(f"Registered experiment: {experiment_id} ({title})")

    def get_experiment(self, experiment_id: str) -> Optional[dict[str, Any]]:
        """
        Get single experiment details.

        Args:
            experiment_id: Experiment identifier

        Returns:
            Experiment entry or None if not found
        """
        return self._index["experiments"].get(experiment_id)

    def get_experiments(
        self,
        status: Optional[str] = None,
        system: Optional[str] = None,
        risk_level: Optional[str] = None,
        tag: Optional[str] = None,
        date_range: Optional[tuple[datetime, datetime]] = None,
        title_contains: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query experiments with optional filters.

        Args:
            status: Filter by status (completed, failed, aborted)
            system: Filter by system (e.g., 'postgresql', 'kafka')
            risk_level: Filter by risk level
            tag: Filter by tag
            date_range: Tuple of (start_date, end_date) to filter
            title_contains: Filter by title substring
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching experiment entries
        """
        results = []

        for exp_id, exp in self._index["experiments"].items():
            # Apply filters
            if status and exp.get("status") != status:
                continue

            if system and system not in exp.get("systems", []):
                continue

            if risk_level and exp.get("risk_level") != risk_level:
                continue

            if tag and tag not in exp.get("tags", []):
                continue

            if (
                title_contains
                and title_contains.lower() not in exp.get("title", "").lower()
            ):
                continue

            if date_range:
                start_date, end_date = date_range
                exp_start = exp.get("start_time")
                if exp_start:
                    try:
                        exp_start_dt = datetime.fromisoformat(exp_start)
                        if exp_start_dt < start_date or exp_start_dt > end_date:
                            continue
                    except ValueError:
                        pass

            results.append(exp)

        # Sort by start_time descending (newest first)
        results.sort(
            key=lambda x: x.get("start_time", ""),
            reverse=True,
        )

        # Apply pagination
        return results[offset : offset + limit]

    def get_experiment_count(
        self,
        status: Optional[str] = None,
        system: Optional[str] = None,
    ) -> int:
        """
        Get count of experiments matching filters.

        Args:
            status: Filter by status
            system: Filter by system

        Returns:
            Count of matching experiments
        """
        return len(self.get_experiments(status=status, system=system, limit=10000))

    def get_systems(self) -> list[str]:
        """
        Get list of all unique systems across experiments.

        Returns:
            Sorted list of system names
        """
        systems = set()
        for exp in self._index["experiments"].values():
            systems.update(exp.get("systems", []))
        return sorted(list(systems))

    def get_statistics(self) -> dict[str, Any]:
        """
        Get aggregate statistics across all experiments.

        Returns:
            Dictionary with statistics
        """
        experiments = list(self._index["experiments"].values())

        if not experiments:
            return {
                "total_experiments": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
                "systems_tested": [],
                "risk_distribution": {},
            }

        successful = sum(
            1 for e in experiments if e.get("status") in ("completed", "success")
        )
        failed = sum(1 for e in experiments if e.get("status") == "failed")
        durations = [
            e.get("duration_seconds")
            for e in experiments
            if e.get("duration_seconds") is not None
        ]

        # Risk distribution
        risk_dist = {}
        for exp in experiments:
            risk = exp.get("risk_level", "unknown")
            risk_dist[risk] = risk_dist.get(risk, 0) + 1

        return {
            "total_experiments": len(experiments),
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / len(experiments) * 100)
            if experiments
            else 0.0,
            "avg_duration_seconds": sum(durations) / len(durations)
            if durations
            else 0.0,
            "systems_tested": self.get_systems(),
            "risk_distribution": risk_dist,
        }

    def export_for_grafana(self) -> list[dict[str, Any]]:
        """
        Export index in Grafana JSON datasource compatible format.

        Returns:
            List of experiment entries formatted for Grafana
        """
        results = []

        for exp_id, exp in self._index["experiments"].items():
            # Convert to Grafana-friendly format
            entry = {
                "experiment_id": exp.get("experiment_id"),
                "title": exp.get("title"),
                "status": exp.get("status"),
                "start_time": exp.get("start_time"),
                "end_time": exp.get("end_time"),
                "duration": exp.get("duration_seconds"),
                "systems": ",".join(exp.get("systems", [])),
                "risk_level": exp.get("risk_level", ""),
                "complexity": exp.get("complexity_score", 0),
                "dashboard_url": exp.get("dashboard_url", ""),
                "report_html": exp.get("report_paths", {}).get("html", ""),
                "report_json": exp.get("report_paths", {}).get("json", ""),
            }
            results.append(entry)

        return results

    def save_grafana_export(self, output_path: Optional[str] = None) -> str:
        """
        Save Grafana-compatible JSON export.

        Args:
            output_path: Output file path (default: experiment_index_grafana.json)

        Returns:
            Path to the exported file
        """
        if output_path is None:
            output_path = str(self.storage_path / "experiment_index_grafana.json")

        data = self.export_for_grafana()

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Grafana export saved: {output_path}")
        return output_path

    def delete_experiment(self, experiment_id: str) -> bool:
        """
        Delete an experiment from the index.

        Args:
            experiment_id: Experiment identifier

        Returns:
            True if deleted, False if not found
        """
        if experiment_id in self._index["experiments"]:
            del self._index["experiments"][experiment_id]
            self._save_index()
            logger.info(f"Deleted experiment from index: {experiment_id}")
            return True
        return False

    def cleanup_old_experiments(self, max_age_days: int = 90) -> int:
        """
        Remove experiments older than max_age_days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of experiments removed
        """
        cutoff = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        to_delete = []

        for exp_id, exp in self._index["experiments"].items():
            start_time = exp.get("start_time")
            if start_time:
                try:
                    exp_time = datetime.fromisoformat(start_time).timestamp()
                    if exp_time < cutoff:
                        to_delete.append(exp_id)
                except ValueError:
                    pass

        for exp_id in to_delete:
            del self._index["experiments"][exp_id]

        if to_delete:
            self._save_index()
            logger.info(f"Cleaned up {len(to_delete)} old experiments")

        return len(to_delete)
