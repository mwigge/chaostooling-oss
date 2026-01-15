# Chaos Toolkit settings.yaml Reference

Chaos Toolkit uses a `settings.yaml` file located at `~/.chaostoolkit/settings.yaml` (or `$HOME/.chaostoolkit/settings.yaml`) to configure global settings.

## Configuration Options

### General Settings

```yaml
# Enable verbose logging
verbose: false

# Enable debug mode
debug: false

# Default timeout for actions and probes (in seconds)
timeout: 30

# Enable dry-run mode (simulate without executing)
dry: false

# Path to journal file
journal_path: null

# Journal format (json or yaml)
journal_format: json
```

### Notifications

```yaml
# Email notifications
notifications:
  email:
    enabled: false
    smtp_host: smtp.example.com
    smtp_port: 587
    smtp_user: null
    smtp_password: null
    from: chaos@example.com
    to: []
    tls: true

# Slack notifications
notifications:
  slack:
    enabled: false
    token: null
    channel: null
    username: "Chaos Toolkit"
    icon_emoji: ":robot_face:"

# Webhook notifications
notifications:
  webhook:
    enabled: false
    url: null
    method: POST
    headers: {}
```

### Controls

```yaml
# Control configuration
controls:
  # HTTP control
  http:
    timeout: 30
    verify_ssl: true

  # Kubernetes control
  kubernetes:
    context: null
    namespace: null
    verify_ssl: true

  # AWS control
  aws:
    region: us-east-1
    profile: null
    verify_ssl: true
```

### Extensions

```yaml
# Extension paths (for custom extensions)
extension_paths: []

# Disable specific extensions
disabled_extensions: []
```

### Output and Reporting

```yaml
# Output directory for reports
output_dir: ./chaos-reports

# Report formats (html, json, pdf)
report_formats:
  - html
  - json

# Enable experiment journaling
journal_enabled: true

# Journal retention (number of experiments to keep)
journal_retention: 100
```

### Security

```yaml
# Enable security checks
security:
  enabled: true
  
  # Require authentication for actions
  require_auth: false
  
  # Allowed action types
  allowed_actions: []
  
  # Blocked action types
  blocked_actions: []
```

### Logging

```yaml
# Logging configuration
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(message)s"
  file: null
  console: true
```

### Experiment Settings

```yaml
# Default experiment settings
experiment:
  # Default steady-state hypothesis tolerance
  tolerance: 0
  
  # Enable rollbacks by default
  rollbacks_enabled: true
  
  # Default rollback strategy
  rollback_strategy: default
  
  # Enable parallel execution
  parallel: false
  
  # Maximum parallel actions
  max_parallel: 5
```

### Plugin Settings

```yaml
# Plugin configuration
plugins:
  # Enable plugin discovery
  discovery_enabled: true
  
  # Plugin paths
  paths: []
  
  # Disabled plugins
  disabled: []
```

## Example settings.yaml

```yaml
verbose: false
debug: false
timeout: 60

notifications:
  email:
    enabled: false
  slack:
    enabled: false
  webhook:
    enabled: false

controls:
  http:
    timeout: 30
    verify_ssl: true

output_dir: ./chaos-reports
report_formats:
  - html
  - json

journal_enabled: true
journal_retention: 100

logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(message)s"
  console: true

experiment:
  tolerance: 0
  rollbacks_enabled: true
  parallel: false
```

## Environment Variables

Many settings can also be configured via environment variables:

- `CHAOSTOOLKIT_VERBOSE` - Enable verbose output
- `CHAOSTOOLKIT_DEBUG` - Enable debug mode
- `CHAOSTOOLKIT_TIMEOUT` - Default timeout
- `CHAOSTOOLKIT_DRY` - Enable dry-run mode
- `CHAOSTOOLKIT_JOURNAL_PATH` - Path to journal file
- `CHAOSTOOLKIT_OUTPUT_DIR` - Output directory for reports

## Location

The settings file is typically located at:
- Linux/macOS: `~/.chaostoolkit/settings.yaml`
- Windows: `%USERPROFILE%\.chaostoolkit\settings.yaml`

You can override the location using the `CHAOSTOOLKIT_SETTINGS_PATH` environment variable.

