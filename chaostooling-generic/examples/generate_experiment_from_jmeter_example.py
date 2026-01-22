#!/usr/bin/env python3
"""
Example script demonstrating how to generate chaos experiments from JMeter test plans.

This script shows:
1. How to parse a JMeter test plan
2. How to generate a chaos experiment from parsed data
3. How to inspect the generated experiment
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chaosgeneric.actions import (
    generate_chaos_experiment_from_jmeter,
    generate_experiment_from_jmeter_cli,
    JMeterTestPlanParser,
)


def example_parse_only():
    """Example: Parse JMeter test plan without generating experiment."""
    print("=" * 60)
    print("Example 1: Parse JMeter Test Plan")
    print("=" * 60)

    # Replace with your actual JMeter test plan path
    jmeter_test_plan = "/path/to/your/test-plan.jmx"

    try:
        parser = JMeterTestPlanParser(jmeter_test_plan)
        jmeter_data = parser.parse()

        print(f"\nTest Plan: {jmeter_data['test_plan']['name']}")
        print(f"Description: {jmeter_data['test_plan']['description']}")
        print(f"\nThread Groups: {len(jmeter_data['thread_groups'])}")
        for tg in jmeter_data['thread_groups']:
            print(f"  - {tg['name']}: {tg['num_threads']} users, "
                  f"{tg['ramp_time']}s ramp-up")

        print(f"\nHTTP Requests: {len(jmeter_data['http_requests'])}")
        for req in jmeter_data['http_requests'][:5]:  # Show first 5
            print(f"  - {req['method']} {req['url']}")

        print(f"\nUnique Endpoints: {len(jmeter_data['endpoints'])}")
        for ep in jmeter_data['endpoints']:
            print(f"  - {ep['url']} ({ep['service_type']})")

        print(f"\nLoad Configuration:")
        load_config = jmeter_data['load_config']
        print(f"  - Total Users: {load_config['total_users']}")
        print(f"  - Ramp-up Time: {load_config['ramp_up_time']}s")
        print(f"  - Duration: {load_config['duration']}s")
        print(f"  - Estimated Duration: {load_config['estimated_duration']}s")

    except FileNotFoundError:
        print(f"Error: JMeter test plan not found: {jmeter_test_plan}")
        print("Please update the path in the script.")
    except Exception as e:
        print(f"Error parsing JMeter test plan: {e}")


def example_generate_experiment():
    """Example: Generate chaos experiment from JMeter test plan."""
    print("\n" + "=" * 60)
    print("Example 2: Generate Chaos Experiment")
    print("=" * 60)

    # Replace with your actual paths
    jmeter_test_plan = "/path/to/your/test-plan.jmx"
    output_experiment = "/tmp/generated-chaos-experiment.json"

    try:
        result = generate_chaos_experiment_from_jmeter(
            jmeter_test_plan_path=jmeter_test_plan,
            output_path=output_experiment,
            experiment_title="My Custom Chaos Experiment",
        )

        print(f"\nGenerated experiment: {result['output_file']}")
        print(f"Experiment title: {result['experiment']['title']}")
        print(f"Tags: {', '.join(result['experiment']['tags'])}")
        print(f"Method steps: {len(result['experiment']['method'])}")

        # Show discovered services
        endpoints = result['jmeter_data']['endpoints']
        service_types = {ep.get('service_type', 'unknown') for ep in endpoints}
        print(f"\nDiscovered service types: {', '.join(sorted(service_types))}")

        # Show generated chaos scenarios
        print("\nGenerated chaos scenarios:")
        for step in result['experiment']['method']:
            if step.get('name', '').startswith('SCENARIO-'):
                print(f"  - {step['name']}")

    except FileNotFoundError:
        print(f"Error: JMeter test plan not found: {jmeter_test_plan}")
        print("Please update the path in the script.")
    except Exception as e:
        print(f"Error generating experiment: {e}")


def example_cli_wrapper():
    """Example: Use CLI-friendly wrapper."""
    print("\n" + "=" * 60)
    print("Example 3: CLI Wrapper")
    print("=" * 60)

    # Replace with your actual path
    jmeter_test_plan = "/path/to/your/test-plan.jmx"

    try:
        output_file = generate_experiment_from_jmeter_cli(
            jmeter_test_plan_path=jmeter_test_plan,
            output_dir="/tmp",
            experiment_title="CLI Generated Experiment",
        )

        print(f"\nGenerated experiment: {output_file}")

        # Load and display experiment summary
        with open(output_file, 'r') as f:
            experiment = json.load(f)

        print(f"\nExperiment Summary:")
        print(f"  Title: {experiment['title']}")
        print(f"  Description: {experiment['description'][:100]}...")
        print(f"  Controls: {len(experiment['controls'])}")
        print(f"  Steady-state probes: {len(experiment['steady-state-hypothesis']['probes'])}")
        print(f"  Method steps: {len(experiment['method'])}")

    except FileNotFoundError:
        print(f"Error: JMeter test plan not found: {jmeter_test_plan}")
        print("Please update the path in the script.")
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("JMeter to Chaos Experiment Generator - Examples")
    print("=" * 60)
    print("\nNote: Update the JMeter test plan paths in the script before running.")
    print("\nThese examples demonstrate:")
    print("  1. Parsing JMeter test plans")
    print("  2. Generating chaos experiments")
    print("  3. Using the CLI wrapper")

    # Uncomment the examples you want to run:
    # example_parse_only()
    # example_generate_experiment()
    # example_cli_wrapper()

    print("\n" + "=" * 60)
    print("To run examples, uncomment the function calls in main()")
    print("and update the JMeter test plan paths.")
    print("=" * 60)


if __name__ == "__main__":
    main()

