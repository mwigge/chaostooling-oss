# Integration Guide

## Overview

This guide explains how chaostooling-demo integrates with external repositories and services.

## External Dependencies

### chaostooling-otel-collector

The OTEL collector is now in a separate repository: `../chaostooling-otel-collector/`

**Integration**:
- Build path: `../chaostooling-otel-collector/otel-collector`
- Config path: `../chaostooling-otel-collector/otel-collector/config.yaml`

**Usage**:
```bash
# Build collector
docker-compose build otel-collector

# Start collector
docker-compose up -d otel-collector
```

### chaostooling-platform-db

The platform database is now in a separate repository: `../chaostooling-platform-db/`

**Integration**:
- Init script: `../chaostooling-platform-db/postgres/init-chaos-platform.sql`

**Usage**:
```bash
# Start database
docker-compose up -d chaos-platform-db

# Verify
psql -h localhost -p 5434 -U chaos_admin -d chaos_platform -c "SELECT 1"
```

## Setup Options

### Option 1: Local Directories (Current)

Repositories are in sibling directories:
```
chaostooling-oss/
├── chaostooling-demo/
├── chaostooling-otel-collector/
└── chaostooling-platform-db/
```

**Pros**: Easy development, no additional setup  
**Cons**: Requires specific directory structure

### Option 2: Git Submodules

Add as git submodules:

```bash
cd chaostooling-demo
git submodule add <repo-url> chaostooling-otel-collector
git submodule add <repo-url> chaostooling-platform-db
```

Update docker-compose.yml paths accordingly.

**Pros**: Version control, easy updates  
**Cons**: Requires submodule management

### Option 3: External Services

Deploy repositories as separate services and connect via network.

**Pros**: Production-ready, independent scaling  
**Cons**: Requires separate deployment

## Environment Variables

### OTEL Collector

No changes needed - uses same environment variables.

### Platform DB

Connection variables:
- `CHAOS_DB_HOST=chaos-platform-db`
- `CHAOS_DB_PORT=5432`
- `CHAOS_DB_NAME=chaos_platform`
- `CHAOS_DB_USER=chaos_admin`
- `CHAOS_DB_PASSWORD=chaos_admin_secure_password`

## Troubleshooting

### Path Not Found

If Docker Compose can't find paths:

1. Verify directory structure
2. Check relative paths in docker-compose.yml
3. Use absolute paths if needed
4. Check Docker build context

### Build Failures

If builds fail:

1. Verify repositories exist
2. Check file permissions
3. Verify Docker build context
4. Check build logs

## Migration Notes

- Original files remain in place for reference
- Can switch back by reverting docker-compose.yml
- Test thoroughly before removing original files

## References

- [OTEL Collector Integration](../chaostooling-otel-collector/docs/INTEGRATION.md)
- [Platform DB Integration](../chaostooling-platform-db/docs/INTEGRATION.md)
