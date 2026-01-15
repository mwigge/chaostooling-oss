# chaostooling-generic

Generic chaos engineering controls and utilities for Chaos Toolkit.

This package provides general-purpose controls and actions that can be used across different types of chaos experiments, regardless of the target system (databases, networks, compute, etc.).

## Controls

### Environment Loader Control

Automatically loads environment variables from `.env` files before running experiments.

**Module:** `chaosgeneric.control.env_loader_control`

See [control/README_ENV_LOADER.md](chaosgeneric/control/README_ENV_LOADER.md) for detailed documentation.

### Load Generator Control

Automatically starts and stops background transaction load generators during experiments.

**Module:** `chaosgeneric.control.load_generator_control`

## Actions

### Load Generator Actions

Actions for controlling background transaction load generators.

**Module:** `chaosgeneric.actions.load_generator.transaction_load_generator`

Functions:
- `start_background_transaction_load()` - Start load generator
- `stop_background_transaction_load()` - Stop load generator
- `get_background_load_stats()` - Get current statistics

## Installation

```bash
pip install chaostooling-generic
```

## Usage

### Environment Loader Control

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

### Load Generator Control

```json
{
  "controls": [
    {
      "name": "load_generator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.load_generator_control"
      },
      "configuration": {
        "load_generator_url": "http://transaction-load-generator:5001",
        "load_generator_tps": 2.0,
        "auto_start_load_generator": "true"
      }
    }
  ]
}
```

## Dependencies

- `requests>=2.31.0` - For HTTP requests to load generator service

## License

Apache-2.0

