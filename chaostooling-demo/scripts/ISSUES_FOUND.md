# Issues Found in Production-Scale Experiment

## ✅ Fixed Issues

### 1. MongoDB Inventory Not Initialized
**Problem**: All purchase requests failed with "Item out of stock" because MongoDB had no inventory items.

**Root Cause**: MongoDB container didn't have initialization script.

**Fix**: 
- Created `init-mongodb-inventory.js` that seeds 100 items (item_0 through item_99) with 1000 units each
- Mounted to `/docker-entrypoint-initdb.d/` in docker-compose.yml
- **Will run automatically** when MongoDB container starts for the first time

**Status**: ✅ Fixed - MongoDB will auto-initialize on `docker compose up -d --build`

### 2. Report Filenames Using "unknown"
**Problem**: Reports were named `unknown_20260108_143319_*.html` instead of using experiment title.

**Root Cause**: Experiment ID not found in journal, no fallback to title.

**Fix**: Updated report generator to:
1. Try journal experiment ID
2. Fall back to experiment title (sanitized)
3. Final fallback to "chaos-experiment"

**Status**: ✅ Fixed

## ⚠️ Non-Critical Issues (Work but semantically incorrect)

### 3. Using `postgres_replication` Module for Non-PostgreSQL Services
**Problem**: Experiment uses `chaosdb.actions.postgres.postgres_replication` functions (`stop_replica`, `start_replica`) for:
- Kafka containers
- App-server containers  
- HA-Proxy containers

**Why it works**: These functions use Docker commands that work with any container, not just PostgreSQL.

**Why it's wrong**: Semantically incorrect - these are generic container start/stop functions but are in a PostgreSQL-specific module.

**Impact**: Low - functions work correctly, just poor organization.

**Recommendation**: Consider creating a generic `chaosdb.actions.compute.container` module for container operations, but not urgent.

**Status**: ⚠️ Works but could be improved

## 📋 Summary

### Critical Issues: 0
### Fixed Issues: 2
### Non-Critical Issues: 1

## Next Steps

1. **Test MongoDB initialization**: 
   ```bash
   docker compose down -v  # Remove volumes to test fresh init
   docker compose up -d --build mongodb
   # Wait a few seconds, then check:
   docker compose exec mongodb mongosh test --eval "db.inventory.countDocuments()"
   ```

2. **Run experiment again** - Should now have successful transactions instead of "Item out of stock" errors.

3. **Consider refactoring** - Move container start/stop functions to a generic compute module (optional, low priority).

