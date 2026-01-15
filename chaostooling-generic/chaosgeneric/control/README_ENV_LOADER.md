# Environment Loader Control

A Chaos Toolkit control that automatically loads environment variables from a `.env` file before running an experiment.

## Features

- Automatically finds and loads `.env` files matching your experiment name
- Supports standard `.env` file format (KEY=value)
- Environment variables already set take precedence (won't override)
- Works seamlessly with Chaos Toolkit's configuration system

## Usage

### 1. Add the Control to Your Experiment

Add the `env-loader` control to your experiment's `controls` section:

```json
{
  "controls": [
    {
      "name": "env-loader",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.env_loader_control"
      }
    }
  ]
}
```

**Important:** Place the `env-loader` control **before** other controls (like `opentelemetry`) so environment variables are loaded first.

### 2. Create a `.env` File

Create a `.env` file with the same name as your experiment file:

- For `test-kafka-topic-saturation.json` → create `test-kafka-topic-saturation.env`
- For `production-scale-distributed-transaction-experiment.json` → create `production-scale-distributed-transaction-experiment.env`

Or create a generic `.env` file in the same directory or current working directory.

### 3. Define Environment Variables

Add your environment variables to the `.env` file:

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC=test

# Database Configuration
POSTGRES_HOST=postgres-primary
POSTGRES_PORT=5432
POSTGRES_DB=testdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# OpenTelemetry Configuration
OTEL_SERVICE_NAME=my-chaos-experiment
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### 4. Run Your Experiment

Simply run your experiment as usual:

```bash
chaos run kafka/test-kafka-topic-saturation.json
```

The control will automatically load environment variables from the `.env` file before the experiment starts.

## How It Works

1. **File Discovery**: The control looks for `.env` files in this order:
   - `<experiment-name>.env` in the same directory as the experiment file
   - `.env` in the same directory as the experiment file
   - `.env` in the current working directory

2. **Variable Loading**: Environment variables are loaded in `before_experiment_control` hook, which runs before steady-state hypothesis validation.

3. **Precedence**: Environment variables already set in the environment take precedence. Variables from the `.env` file are only set if they don't already exist.

## Configuration Options

You can optionally specify a custom `.env` file path in the control configuration:

```json
{
  "controls": [
    {
      "name": "env-loader",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.env_loader_control"
      },
      "configuration": {
        "env_file": "/path/to/custom.env"
      }
    }
  ]
}
```

## Example

See `chaostooling-experiments/kafka/test-kafka-topic-saturation.json` for a complete example.

The corresponding `.env` file would be `test-kafka-topic-saturation.env`:

```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC=test
OTEL_SERVICE_NAME=kafka-topic-saturation-test
```

## Benefits

- **Self-contained experiments**: All configuration in one place
- **Easy environment switching**: Different `.env` files for different environments
- **No manual export**: No need to manually export variables before running experiments
- **Version control friendly**: `.env` files can be gitignored while `.env.example` files document required variables

## Notes

- The `.env` file format supports:
  - `KEY=value` (simple values)
  - `KEY="value with spaces"` (quoted values)
  - `# comments` (comments)
  - Empty lines are ignored

- Variables with quotes are automatically unquoted
- Existing environment variables are never overridden

