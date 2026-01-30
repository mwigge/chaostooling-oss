#!/bin/bash
# Debug script to troubleshoot OpenTelemetry PostgreSQL metrics

set -e

echo "OpenTelemetry PostgreSQL Metrics Debugging"
echo "=========================================="
echo ""

# Configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if Prometheus is accessible
echo "[STEP 1] Checking Prometheus connectivity..."
if curl -s "$PROMETHEUS_URL/-/healthy" > /dev/null; then
    echo -e "${GREEN}[OK]${NC} Prometheus is accessible at $PROMETHEUS_URL"
else
    echo -e "${RED}[FAIL]${NC} Cannot connect to Prometheus at $PROMETHEUS_URL"
    exit 1
fi
echo ""

# Step 2: List available metrics
echo "[STEP 2] Checking for PostgreSQL metrics in Prometheus..."
POSTGRES_METRICS=$(curl -s "$PROMETHEUS_URL/api/v1/label/__name__/values" | \
    grep -o '"postgres[^"]*"' | wc -l)

if [ "$POSTGRES_METRICS" -gt 0 ]; then
    echo -e "${GREEN}[OK]${NC} Found $POSTGRES_METRICS PostgreSQL-related metrics"
    echo ""
    echo "Available PostgreSQL metrics:"
    curl -s "$PROMETHEUS_URL/api/v1/label/__name__/values" | \
        grep -o '"postgres[^"]*"' | sort | head -20
else
    echo -e "${RED}[FAIL]${NC} No PostgreSQL metrics found in Prometheus"
    echo ""
    echo "Checking for postgres_exporter metrics..."
    PG_EXPORTER=$(curl -s "$PROMETHEUS_URL/api/v1/label/__name__/values" | \
        grep -o '"pg_[^"]*"' | wc -l)
    
    if [ "$PG_EXPORTER" -gt 0 ]; then
        echo -e "${YELLOW}[INFO]${NC} Found $PG_EXPORTER pg_* metrics (using postgres_exporter)"
    else
        echo -e "${RED}[WARNING]${NC} No PostgreSQL metrics at all. Check:"
        echo "  1. OpenTelemetry Collector PostgreSQL receiver configuration"
        echo "  2. Prometheus scrape_config includes collector endpoint"
        echo "  3. PostgreSQL connection credentials in OTel config"
    fi
fi
echo ""

# Step 3: Query specific metrics
echo "[STEP 3] Querying specific PostgreSQL metrics..."
METRICS=(
    "postgres_stat_activity_count"
    "postgres_queries_total"
    "postgres_database_size_bytes"
    "postgres_table_row_count"
)

for metric in "${METRICS[@]}"; do
    RESULT=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=$metric" | grep -o '"result":\[\]' || true)
    
    if [ -z "$RESULT" ]; then
        SERIES=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=$metric" | grep -o '"result":\[[^]]*\]' || echo "[]")
        if [ "$SERIES" != "[]" ]; then
            echo -e "${GREEN}[OK]${NC} $metric: Data available"
        else
            echo -e "${YELLOW}[EMPTY]${NC} $metric: No data points"
        fi
    else
        echo -e "${RED}[NO DATA]${NC} $metric: Not found"
    fi
done
echo ""

# Step 4: Check Prometheus targets
echo "[STEP 4] Checking Prometheus scrape targets..."
TARGETS=$(curl -s "$PROMETHEUS_URL/api/v1/targets" | grep -o '"job":"[^"]*"' | sort -u)

if echo "$TARGETS" | grep -q "postgres\|otel"; then
    echo -e "${GREEN}[OK]${NC} PostgreSQL/OTel targets found:"
    echo "$TARGETS" | grep "postgres\|otel"
else
    echo -e "${RED}[WARNING]${NC} No PostgreSQL/OTel targets found in Prometheus"
    echo "Available targets:"
    echo "$TARGETS"
fi
echo ""

# Step 5: Test Grafana datasource
echo "[STEP 5] Testing Grafana Prometheus datasource..."
if [ -n "$GRAFANA_API_TOKEN" ]; then
    DATASOURCE=$(curl -s -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
        "$GRAFANA_URL/api/datasources" | grep -i "prometheus" || true)
    
    if [ -n "$DATASOURCE" ]; then
        echo -e "${GREEN}[OK]${NC} Grafana connected to Prometheus datasource"
    else
        echo -e "${RED}[FAIL]${NC} Prometheus datasource not found in Grafana"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} GRAFANA_API_TOKEN not set, skipping Grafana check"
fi
echo ""

# Step 6: Sample query execution
echo "[STEP 6] Executing sample queries..."
echo ""
echo "Query: postgres_stat_activity_count"
curl -s "$PROMETHEUS_URL/api/v1/query?query=postgres_stat_activity_count" | \
    python3 -m json.tool 2>/dev/null | head -30
echo ""

# Step 7: Check OTel Collector logs
echo "[STEP 7] Checking OTel Collector logs for errors..."
if command -v docker &> /dev/null; then
    OTEL_LOGS=$(docker logs otel-collector 2>&1 | grep -i "postgres\|error" | tail -5 || echo "No logs found")
    
    if [ -n "$OTEL_LOGS" ]; then
        echo "Recent OTel logs:"
        echo "$OTEL_LOGS"
    else
        echo -e "${YELLOW}[INFO]${NC} No PostgreSQL-related errors in OTel logs"
    fi
else
    echo -e "${YELLOW}[SKIP]${NC} Docker not available for log inspection"
fi
echo ""

# Step 8: Recommendations
echo "[RECOMMENDATIONS]"
echo ""
echo "If metrics show 'no data' or are missing:"
echo ""
echo "1. Verify OTel PostgreSQL Receiver Configuration:"
echo "   docker exec otel-collector cat /etc/otel-collector-config.yml | grep -A 10 postgres"
echo ""
echo "2. Check PostgreSQL Connection in OTel Config:"
echo "   - endpoint: postgres-primary:5432 (or correct hostname)"
echo "   - username/password match PostgreSQL credentials"
echo "   - Database is accessible from OTel container"
echo ""
echo "3. Verify Prometheus Scrape Config:"
echo "   docker exec prometheus cat /etc/prometheus/prometheus.yml | grep -A 10 otel"
echo ""
echo "4. Test Direct PostgreSQL Connection:"
echo "   docker exec postgres psql -U postgres -c 'SELECT version();'"
echo ""
echo "5. Check Metric Names Match Your PostgreSQL Exporter:"
echo "   - OpenTelemetry: postgres_* (e.g., postgres_stat_activity_count)"
echo "   - postgres_exporter: pg_* (e.g., pg_stat_activity_count)"
echo "   - Use 'avg_over_time(metric[24h])' for 24h baselines"
echo ""
echo "6. Use Longer Time Ranges for Baselines:"
echo "   - Pre-chaos: 24h or 30d (use avg_over_time)"
echo "   - During-chaos: 5m or 1m"
echo "   - Post-chaos: 5m"
echo ""
