"""
Action to generate chaos experiments from JMeter test plans.

This is the main entry point for the feature that combines:
1. Parsing JMeter test plans (.jmx files)
2. Extracting endpoints and service patterns
3. Generating chaos experiments that combine load testing with chaos scenarios
"""

import logging
from pathlib import Path
from typing import Any, Optional

from .experiment_generator import ChaosExperimentGenerator
from .jmeter_parser import JMeterTestPlanParser

logger = logging.getLogger("chaosgeneric.actions.generate_experiment_from_jmeter")


def generate_chaos_experiment_from_jmeter(
    jmeter_test_plan_path: str,
    output_path: Optional[str] = None,
    experiment_title: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate a chaos experiment from a JMeter test plan.

    This function:
    1. Parses the JMeter test plan (.jmx) to extract endpoints, thread groups, and configuration
    2. Identifies service types (databases, messaging, applications) from discovered endpoints
    3. Generates a complete Chaos Toolkit experiment JSON that:
       - Uses JMeter as the load generator (via jmeter_gatling_control)
       - Includes chaos scenarios targeting discovered services
       - Integrates observability (OTEL traces, metrics, logs)
       - Combines load testing with chaos engineering for realistic scenarios

    Args:
        jmeter_test_plan_path: Path to JMeter test plan (.jmx file)
        output_path: Path to write generated experiment JSON (optional)
                     If not provided, returns experiment dict without writing
        experiment_title: Custom title for the generated experiment (optional)
                          If not provided, uses test plan name

    Returns:
        Dictionary containing:
        - experiment: Generated chaos experiment JSON structure
        - jmeter_data: Parsed JMeter test plan data
        - output_file: Path to written file (if output_path provided)

    Example:
        >>> result = generate_chaos_experiment_from_jmeter(
        ...     jmeter_test_plan_path="/path/to/test-plan.jmx",
        ...     output_path="/path/to/generated-experiment.json",
        ...     experiment_title="My Custom Chaos Experiment"
        ... )
        >>> print(f"Generated experiment: {result['output_file']}")
        >>> print(f"Discovered {len(result['jmeter_data']['endpoints'])} endpoints")
    """
    try:
        # Step 1: Parse JMeter test plan
        logger.info(f"Parsing JMeter test plan: {jmeter_test_plan_path}")
        parser = JMeterTestPlanParser(jmeter_test_plan_path)
        jmeter_data = parser.parse()

        logger.info(
            f"Parsed test plan '{jmeter_data['test_plan']['name']}': "
            f"{len(jmeter_data['http_requests'])} HTTP requests, "
            f"{len(jmeter_data['endpoints'])} unique endpoints, "
            f"{len(jmeter_data['thread_groups'])} thread groups"
        )

        # Step 2: Generate chaos experiment
        logger.info("Generating chaos experiment from parsed data")
        generator = ChaosExperimentGenerator(
            jmeter_data=jmeter_data,
            output_path=output_path,
            experiment_title=experiment_title,
        )
        experiment = generator.generate()

        result = {
            "experiment": experiment,
            "jmeter_data": jmeter_data,
        }

        if output_path:
            result["output_file"] = str(Path(output_path).absolute())
            logger.info(f"Generated chaos experiment: {output_path}")

        # Log summary
        endpoints = jmeter_data.get("endpoints", [])
        service_types = {ep.get("service_type", "unknown") for ep in endpoints}
        logger.info(
            f"Generated experiment '{experiment['title']}' with "
            f"{len(experiment['method'])} method steps targeting "
            f"{len(service_types)} service types: {', '.join(sorted(service_types))}"
        )

        return result

    except FileNotFoundError as e:
        logger.error(f"JMeter test plan not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to generate chaos experiment from JMeter test plan: {e}")
        raise


def generate_experiment_from_jmeter_cli(
    jmeter_test_plan_path: str,
    output_dir: Optional[str] = None,
    experiment_title: Optional[str] = None,
) -> str:
    """
    CLI-friendly wrapper that generates experiment and returns output path.

    Args:
        jmeter_test_plan_path: Path to JMeter test plan (.jmx file)
        output_dir: Directory to write generated experiment (optional)
                    If not provided, writes to same directory as test plan
        experiment_title: Custom title for the generated experiment (optional)

    Returns:
        Path to generated experiment JSON file
    """
    test_plan_path = Path(jmeter_test_plan_path)

    if not output_dir:
        output_dir = test_plan_path.parent

    output_path = Path(output_dir) / f"{test_plan_path.stem}-chaos-experiment.json"

    result = generate_chaos_experiment_from_jmeter(
        jmeter_test_plan_path=str(test_plan_path),
        output_path=str(output_path),
        experiment_title=experiment_title,
    )

    return result["output_file"]

