"""
Chaos experiment generator from JMeter test plan data.

Generates Chaos Toolkit experiment JSON files that combine:
- JMeter load testing (via jmeter_gatling_control)
- Chaos engineering scenarios targeting discovered services
- Observability integration (OTEL traces, metrics, logs)
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chaosgeneric.actions.experiment_generator")


class ChaosExperimentGenerator:
    """Generate chaos experiments from parsed JMeter test plan data."""

    def __init__(
        self,
        jmeter_data: dict[str, Any],
        output_path: Optional[str] = None,
        experiment_title: Optional[str] = None,
    ):
        """
        Initialize generator with parsed JMeter data.

        Args:
            jmeter_data: Parsed JMeter test plan data from JMeterTestPlanParser
            output_path: Path to write generated experiment JSON (optional)
            experiment_title: Custom experiment title (optional)
        """
        self.jmeter_data = jmeter_data
        self.output_path = Path(output_path) if output_path else None
        self.experiment_title = experiment_title

    def generate(self) -> dict[str, Any]:
        """
        Generate a complete chaos experiment JSON structure.

        Returns:
            Dictionary representing the chaos experiment
        """
        test_plan = self.jmeter_data.get("test_plan", {})
        endpoints = self.jmeter_data.get("endpoints", [])
        load_config = self.jmeter_data.get("load_config", {})

        title = (
            self.experiment_title
            or f"{test_plan.get('name', 'JMeter')} Chaos Experiment"
        )

        experiment = {
            "version": "1.0.0",
            "title": title,
            "description": self._build_description(test_plan, endpoints, load_config),
            "tags": self._generate_tags(endpoints),
            "configuration": self._generate_configuration(),
            "controls": self._generate_controls(),
            "steady-state-hypothesis": self._generate_steady_state_hypothesis(endpoints),
            "method": self._generate_method(endpoints, load_config),
            "rollbacks": self._generate_rollbacks(),
        }

        if self.output_path:
            self._write_experiment(experiment)

        return experiment

    def _build_description(
        self,
        test_plan: dict[str, Any],
        endpoints: list[dict[str, Any]],
        load_config: dict[str, Any],
    ) -> str:
        """Build experiment description."""
        base_desc = test_plan.get("description", "")
        if base_desc:
            base_desc += " "

        desc = (
            f"{base_desc}Chaos engineering experiment automatically generated from "
            f"JMeter test plan '{test_plan.get('name', 'Unknown')}'. "
            f"Combines load testing ({load_config.get('total_users', 1)} users) "
            f"with chaos scenarios targeting {len(endpoints)} discovered endpoints. "
            f"Tests system resilience under realistic load conditions."
        )

        return desc.strip()

    def _generate_tags(self, endpoints: list[dict[str, Any]]) -> list[str]:
        """Generate tags based on discovered services."""
        tags = ["jmeter", "load-testing", "chaos", "resilience", "observability", "auto-generated"]

        service_types = {ep.get("service_type", "application") for ep in endpoints}
        for service_type in service_types:
            if service_type.startswith("database_"):
                tags.append("database")
                tags.append(service_type.replace("database_", ""))
            elif service_type.startswith("messaging_"):
                tags.append("messaging")
                tags.append(service_type.replace("messaging_", ""))
            elif service_type == "load_balancer":
                tags.append("infrastructure")
            else:
                tags.append("application")

        return list(set(tags))

    def _generate_configuration(self) -> dict[str, Any]:
        """Generate experiment configuration section."""
        test_plan = self.jmeter_data.get("test_plan", {})
        load_config = self.jmeter_data.get("load_config", {})

        config = {
            "_comment": "=== JMETER LOAD GENERATOR CONFIGURATION ===",
            "jmeter_test_plan": {
                "type": "env",
                "key": "JMETER_TEST_PLAN",
                "default": str(self.jmeter_data.get("test_plan", {}).get("filename", "")),
            },
            "jmeter_home": {
                "type": "env",
                "key": "JMETER_HOME",
                "default": "/opt/apache-jmeter",
            },
            "auto_start_load_generator": {
                "type": "env",
                "key": "AUTO_START_LOAD_GENERATOR",
                "default": "true",
            },
            "_comment2": "=== CHAOS PARAMETERS ===",
            "stress_duration": {
                "type": "env",
                "key": "STRESS_DURATION",
                "default": str(load_config.get("estimated_duration", 300)),
            },
            "num_threads": {
                "type": "env",
                "key": "NUM_THREADS",
                "default": "10",
            },
            "_comment3": "=== OBSERVABILITY ===",
            "otel_service_name": {
                "type": "env",
                "key": "OTEL_SERVICE_NAME",
                "default": f"{test_plan.get('name', 'jmeter-chaos').lower().replace(' ', '-')}-experiment",
            },
            "_comment4": "=== REPORTING ===",
            "reporting_output_dir": {
                "type": "env",
                "key": "CHAOS_REPORTING_OUTPUT_DIR",
                "default": "/var/log/chaostoolkit/reports",
            },
            "reporting_formats": {
                "type": "env",
                "key": "CHAOS_REPORTING_FORMATS",
                "default": "html,json",
            },
        }

        # Add endpoint-specific configurations
        endpoints = self.jmeter_data.get("endpoints", [])
        for i, endpoint in enumerate(endpoints[:5]):  # Limit to first 5 for brevity
            host_key = f"endpoint_{i+1}_host"
            config[host_key] = {
                "type": "env",
                "key": f"ENDPOINT_{i+1}_HOST",
                "default": endpoint.get("host", ""),
            }

        return config

    def _generate_controls(self) -> list[dict[str, Any]]:
        """Generate controls section."""
        return [
            {
                "name": "env-loader",
                "provider": {
                    "type": "python",
                    "module": "chaosgeneric.control.env_loader_control",
                },
            },
            {
                "name": "opentelemetry",
                "provider": {
                    "type": "python",
                    "module": "chaosotel.control",
                },
            },
            {
                "name": "reporting",
                "provider": {
                    "type": "python",
                    "module": "chaostooling_reporting.control",
                },
            },
            {
                "name": "jmeter_load_generator",
                "provider": {
                    "type": "python",
                    "module": "chaosgeneric.control.jmeter_gatling_control",
                },
                "configuration": {
                    "tool": "jmeter",
                    "auto_start_load_generator": "${auto_start_load_generator}",
                    "jmeter_test_plan": "${jmeter_test_plan}",
                    "jmeter_home": "${jmeter_home}",
                },
            },
        ]

    def _generate_steady_state_hypothesis(
        self, endpoints: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate steady-state hypothesis probes."""
        probes = []

        # Add health check for each unique service
        seen_services = set()
        for endpoint in endpoints:
            service_type = endpoint.get("service_type", "application")
            if service_type in seen_services:
                continue
            seen_services.add(service_type)

            if service_type == "application" or service_type.startswith("database_") or service_type.startswith("messaging_"):
                probe = self._create_service_probe(endpoint, service_type)
                if probe:
                    probes.append(probe)

        if not probes:
            # Fallback: generic HTTP probe
            if endpoints:
                first_endpoint = endpoints[0]
                probes.append({
                    "name": "probe-endpoint-availability",
                    "type": "probe",
                    "provider": {
                        "type": "http",
                        "url": first_endpoint.get("url", ""),
                        "method": "GET",
                        "timeout": 5,
                    },
                    "tolerance": 200,
                })

        return {
            "title": "System is healthy and endpoints are accessible",
            "probes": probes,
        }

    def _create_service_probe(
        self, endpoint: dict[str, Any], service_type: str
    ) -> Optional[dict[str, Any]]:
        """Create a probe for a specific service type."""
        if service_type.startswith("database_postgres"):
            return {
                "name": "probe-postgres-connectivity",
                "type": "probe",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.probes.postgres.postgres_connectivity",
                    "func": "probe_postgres_connectivity",
                    "arguments": {
                        "host": endpoint.get("host", ""),
                        "port": endpoint.get("port", 5432),
                    },
                },
                "tolerance": True,
            }

        elif service_type.startswith("database_mysql"):
            return {
                "name": "probe-mysql-connectivity",
                "type": "probe",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.probes.mysql.mysql_connectivity",
                    "func": "probe_mysql_connectivity",
                    "arguments": {
                        "host": endpoint.get("host", ""),
                        "port": endpoint.get("port", 3306),
                    },
                },
                "tolerance": True,
            }

        elif service_type.startswith("messaging_kafka"):
            return {
                "name": "probe-kafka-connectivity",
                "type": "probe",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.probes.kafka.kafka_connectivity",
                    "func": "probe_kafka_connectivity",
                    "arguments": {
                        "bootstrap_servers": f"{endpoint.get('host', '')}:{endpoint.get('port', 9092)}",
                        "topic": "test",
                    },
                },
                "tolerance": True,
            }

        else:
            # Generic HTTP probe
            return {
                "name": f"probe-{endpoint.get('host', 'unknown')}",
                "type": "probe",
                "provider": {
                    "type": "http",
                    "url": endpoint.get("url", ""),
                    "method": endpoint.get("method", "GET"),
                    "timeout": 5,
                },
                "tolerance": 200,
            }

    def _generate_method(
        self, endpoints: list[dict[str, Any]], load_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate method section with baseline and chaos scenarios."""
        method = []

        # Phase 1: Baseline
        method.append({
            "_comment_phase": "=== PHASE 1: BASELINE - Establish baseline with JMeter load ===",
            "name": "baseline-with-jmeter-load",
            "type": "action",
            "provider": {
                "type": "python",
                "module": "chaosgeneric.actions.load_generator.jmeter_api",
                "func": "get_jmeter_test_status",
                "arguments": {
                    "results_file": "/tmp/jmeter-baseline.jtl",
                },
            },
        })

        # Phase 2: Chaos scenarios based on discovered services
        method.append({
            "_comment_phase": "=== PHASE 2: CHAOS SCENARIOS (During JMeter load) ===",
        })

        # Group endpoints by service type
        service_groups: dict[str, list[dict[str, Any]]] = {}
        for endpoint in endpoints:
            service_type = endpoint.get("service_type", "application")
            if service_type not in service_groups:
                service_groups[service_type] = []
            service_groups[service_type].append(endpoint)

        # Generate chaos scenarios for each service type
        scenario_count = 0
        for service_type, service_endpoints in service_groups.items():
            scenarios = self._generate_service_chaos_scenarios(
                service_type, service_endpoints, scenario_count
            )
            method.extend(scenarios)
            scenario_count += len(scenarios)

        # Phase 3: Final validation
        method.append({
            "_comment_phase": "=== PHASE 3: FINAL VALIDATION ===",
            "name": "verify-system-health-after-chaos",
            "type": "probe",
            "provider": {
                "type": "http",
                "url": endpoints[0].get("url", "") if endpoints else "",
                "method": "GET",
                "timeout": 5,
            },
            "tolerance": 200,
        })

        return method

    def _generate_service_chaos_scenarios(
        self, service_type: str, endpoints: list[dict[str, Any]], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate chaos scenarios for a specific service type."""
        scenarios = []

        if service_type.startswith("database_postgres"):
            scenarios.extend(self._generate_postgres_scenarios(endpoints[0], start_index))
        elif service_type.startswith("database_mysql"):
            scenarios.extend(self._generate_mysql_scenarios(endpoints[0], start_index))
        elif service_type.startswith("messaging_kafka"):
            scenarios.extend(self._generate_kafka_scenarios(endpoints[0], start_index))
        elif service_type.startswith("messaging_rabbitmq"):
            scenarios.extend(self._generate_rabbitmq_scenarios(endpoints[0], start_index))
        else:
            # Generic application/infrastructure scenarios
            scenarios.extend(self._generate_generic_scenarios(endpoints[0], start_index))

        return scenarios

    def _generate_postgres_scenarios(
        self, endpoint: dict[str, Any], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate PostgreSQL chaos scenarios."""
        return [
            {
                "name": f"SCENARIO-{start_index + 1}-PostgreSQL-Connection-Pool-Exhaustion",
                "type": "action",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.actions.postgres.postgres_connection_stress",
                    "func": "inject_connection_stress",
                    "arguments": {
                        "host": endpoint.get("host", ""),
                        "port": endpoint.get("port", 5432),
                        "num_connections": 100,
                        "duration_seconds": "${stress_duration}",
                    },
                },
            },
        ]

    def _generate_mysql_scenarios(
        self, endpoint: dict[str, Any], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate MySQL chaos scenarios."""
        return [
            {
                "name": f"SCENARIO-{start_index + 1}-MySQL-Query-Saturation",
                "type": "action",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.actions.mysql.mysql_query_stress",
                    "func": "inject_query_stress",
                    "arguments": {
                        "host": endpoint.get("host", ""),
                        "port": endpoint.get("port", 3306),
                        "num_threads": "${num_threads}",
                        "duration_seconds": "${stress_duration}",
                    },
                },
            },
        ]

    def _generate_kafka_scenarios(
        self, endpoint: dict[str, Any], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate Kafka chaos scenarios."""
        return [
            {
                "name": f"SCENARIO-{start_index + 1}-Kafka-Message-Flood",
                "type": "action",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.actions.kafka.kafka_message_flood",
                    "func": "inject_message_flood",
                    "arguments": {
                        "bootstrap_servers": f"{endpoint.get('host', '')}:{endpoint.get('port', 9092)}",
                        "topic": "test",
                        "num_producers": 10,
                        "messages_per_producer": 1000,
                        "duration_seconds": "${stress_duration}",
                    },
                },
            },
        ]

    def _generate_rabbitmq_scenarios(
        self, endpoint: dict[str, Any], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate RabbitMQ chaos scenarios."""
        return [
            {
                "name": f"SCENARIO-{start_index + 1}-RabbitMQ-Queue-Saturation",
                "type": "action",
                "provider": {
                    "type": "python",
                    "module": "chaosdb.actions.rabbitmq.rabbitmq_queue_stress",
                    "func": "inject_queue_stress",
                    "arguments": {
                        "host": endpoint.get("host", ""),
                        "port": endpoint.get("port", 5672),
                        "queue": "test",
                        "num_producers": 10,
                        "duration_seconds": "${stress_duration}",
                    },
                },
            },
        ]

    def _generate_generic_scenarios(
        self, endpoint: dict[str, Any], start_index: int
    ) -> list[dict[str, Any]]:
        """Generate generic application/infrastructure chaos scenarios."""
        return [
            {
                "name": f"SCENARIO-{start_index + 1}-Network-Latency",
                "type": "action",
                "provider": {
                    "type": "python",
                    "module": "chaosnetwork.actions.network_latency",
                    "func": "inject_latency",
                    "arguments": {
                        "target": endpoint.get("host", ""),
                        "latency_ms": 500,
                        "duration_seconds": "${stress_duration}",
                    },
                },
            },
        ]

    def _generate_rollbacks(self) -> list[dict[str, Any]]:
        """Generate rollbacks section."""
        return [
            {
                "type": "action",
                "name": "generate-experiment-reports",
                "provider": {
                    "type": "python",
                    "module": "chaostooling_reporting.actions",
                    "func": "generate_experiment_reports",
                    "arguments": {
                        "output_dir": "${reporting_output_dir}",
                        "formats": "${reporting_formats}",
                        "executive": True,
                        "compliance": True,
                        "audit": True,
                        "product_owner": True,
                    },
                },
            },
        ]

    def _write_experiment(self, experiment: dict[str, Any]) -> None:
        """Write experiment to JSON file."""
        if not self.output_path:
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(experiment, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated chaos experiment: {self.output_path}")

