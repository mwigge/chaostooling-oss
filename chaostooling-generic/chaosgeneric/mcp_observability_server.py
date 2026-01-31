"""
MCP Server for Grafana Observability Stack Integration
Enables Claude to query Grafana, Loki, Prometheus, and Tempo

This server provides tools to:
1. Define steady state (baseline metrics analysis)
2. Query observability data (traces, metrics, logs)
3. Generate hypotheses based on system behavior
4. Analyze chaos experiment results
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests
from mcp.server import Server, stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
    ToolResult,
)

# Import shared baseline management functions
try:
    from .tools.baseline_manager import (
        PrometheusClient,
        calculate_statistics,
        parse_time_range,
    )

    BASELINE_MANAGER_AVAILABLE = True
except ImportError:
    BASELINE_MANAGER_AVAILABLE = False
    PrometheusClient = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration from environment
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
TEMPO_URL = os.getenv("TEMPO_URL", "http://localhost:3100")
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")


class ObservabilityClient:
    """Client for querying observability stack"""

    def __init__(self):
        self.grafana_url = GRAFANA_URL
        self.prometheus_url = PROMETHEUS_URL
        self.tempo_url = TEMPO_URL
        self.loki_url = LOKI_URL
        self.grafana_headers = {
            "Authorization": f"Bearer {GRAFANA_TOKEN}",
            "Content-Type": "application/json",
        }

        # Use shared PrometheusClient if available
        if BASELINE_MANAGER_AVAILABLE and PrometheusClient:
            self._prom_client = PrometheusClient(self.prometheus_url)
        else:
            self._prom_client = None

    def query_prometheus(self, query: str, time_range: str = "1h") -> dict:
        """
        Query Prometheus for metrics.

        Args:
            query: PromQL query
            time_range: Time range (e.g., '1h', '24h', '7d')

        Returns:
            Query results with timestamps and values
        """
        # Use shared client if available
        if self._prom_client:
            end_time = datetime.utcnow()
            start_time = end_time - parse_time_range(time_range)
            result = self._prom_client.query_range(query, start_time, end_time)
            if result["status"] == "success":
                result["query"] = query
            return result

        # Fallback to legacy implementation
        try:
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)

            params = {
                "query": query,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": "60",  # 1-minute granularity
            }

            response = requests.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            if data["status"] == "success":
                return {
                    "status": "success",
                    "data": data["data"],
                    "query": query,
                }
            else:
                return {
                    "status": "error",
                    "error": data.get("error", "Unknown error"),
                }
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return {"status": "error", "error": str(e)}

    def query_instant_prometheus(self, query: str) -> dict:
        """
        Query Prometheus instant metrics (current value only).

        Args:
            query: PromQL query

        Returns:
            Current metric values
        """
        try:
            params = {"query": query}
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            if data["status"] == "success":
                return {
                    "status": "success",
                    "data": data["data"],
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                return {
                    "status": "error",
                    "error": data.get("error", "Unknown error"),
                }
        except Exception as e:
            logger.error(f"Prometheus instant query failed: {e}")
            return {"status": "error", "error": str(e)}

    def query_tempo(
        self,
        service_name: Optional[str] = None,
        min_duration: Optional[str] = None,
        time_range: str = "1h",
    ) -> dict:
        """
        Query Tempo for distributed traces.

        Args:
            service_name: Filter by service (optional)
            min_duration: Minimum span duration (e.g., '100ms')
            time_range: Time range to search

        Returns:
            List of traces matching criteria
        """
        try:
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)

            # Build TraceQL query
            traceql_parts = []
            if service_name:
                traceql_parts.append(f'resource.service.name = "{service_name}"')
            if min_duration:
                duration_ms = self._parse_duration_to_ms(min_duration)
                traceql_parts.append(f"duration > {duration_ms}ms")

            traceql = " && ".join(traceql_parts) if traceql_parts else ""

            params = {
                "q": traceql,
                "start": int(start_time.timestamp() * 1_000_000_000),
                "end": int(end_time.timestamp() * 1_000_000_000),
                "limit": 100,
            }

            response = requests.get(
                f"{self.tempo_url}/api/search",
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            return {
                "status": "success",
                "traces": data.get("traces", []),
                "metrics": data.get("metrics", {}),
                "query": traceql,
            }
        except Exception as e:
            logger.error(f"Tempo query failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_trace_detail(self, trace_id: str) -> dict:
        """Get detailed trace information"""
        try:
            response = requests.get(
                f"{self.tempo_url}/api/traces/{trace_id}",
                timeout=30,
            )
            response.raise_for_status()

            return {
                "status": "success",
                "trace": response.json(),
                "trace_id": trace_id,
            }
        except Exception as e:
            logger.error(f"Trace detail query failed: {e}")
            return {"status": "error", "error": str(e)}

    def query_loki(self, query: str, time_range: str = "1h") -> dict:
        """
        Query Loki for logs.

        Args:
            query: LogQL query (e.g., '{service="order-service"}')
            time_range: Time range to search

        Returns:
            Log entries matching query
        """
        try:
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)

            params = {
                "query": query,
                "start": int(start_time.timestamp() * 1_000_000_000),
                "end": int(end_time.timestamp() * 1_000_000_000),
                "limit": 1000,
            }

            response = requests.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            if data["status"] == "success":
                return {
                    "status": "success",
                    "logs": data["data"]["result"],
                    "query": query,
                }
            else:
                return {
                    "status": "error",
                    "error": data.get("error", "Unknown error"),
                }
        except Exception as e:
            logger.error(f"Loki query failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_datasources(self) -> dict:
        """Get list of available Grafana datasources"""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/datasources",
                headers=self.grafana_headers,
                timeout=30,
            )
            response.raise_for_status()

            datasources = response.json()
            return {
                "status": "success",
                "datasources": datasources,
                "count": len(datasources),
            }
        except Exception as e:
            logger.error(f"Datasources query failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_dashboard(self, dashboard_id: str) -> dict:
        """Get Grafana dashboard definition"""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/dashboards/uid/{dashboard_id}",
                headers=self.grafana_headers,
                timeout=30,
            )
            response.raise_for_status()

            return {
                "status": "success",
                "dashboard": response.json(),
                "dashboard_id": dashboard_id,
            }
        except Exception as e:
            logger.error(f"Dashboard query failed: {e}")
            return {"status": "error", "error": str(e)}

    def list_dashboards(self) -> dict:
        """List all Grafana dashboards"""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/search?type=dash-db",
                headers=self.grafana_headers,
                timeout=30,
            )
            response.raise_for_status()

            return {
                "status": "success",
                "dashboards": response.json(),
                "count": len(response.json()),
            }
        except Exception as e:
            logger.error(f"Dashboards list query failed: {e}")
            return {"status": "error", "error": str(e)}

    def _parse_time_range(self, time_range: str, end_time: datetime) -> datetime:
        """Convert time range string to datetime"""
        mapping = {
            "m": "minutes",
            "h": "hours",
            "d": "days",
            "w": "weeks",
        }

        if time_range.endswith(("m", "h", "d", "w")):
            unit = time_range[-1]
            value = int(time_range[:-1])
            delta = timedelta(**{mapping[unit]: value})
            return end_time - delta
        else:
            return end_time - timedelta(hours=1)

    def _parse_duration_to_ms(self, duration: str) -> int:
        """Convert duration string to milliseconds"""
        if duration.endswith("ms"):
            return int(duration[:-2])
        elif duration.endswith("s"):
            return int(duration[:-1]) * 1000
        elif duration.endswith("m"):
            return int(duration[:-1]) * 60 * 1000
        else:
            return int(duration)


# Initialize observability client
observability = ObservabilityClient()


def create_tools() -> list[Tool]:
    """Define MCP tools for observability stack"""

    return [
        Tool(
            name="query_prometheus",
            description="Query Prometheus metrics using PromQL",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query (e.g., 'rate(http_requests_total[5m])')",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range (e.g., '1h', '24h', '7d')",
                        "default": "1h",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_instant_prometheus",
            description="Query current Prometheus metrics (instant query)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL instant query",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_tempo",
            description="Query Tempo for distributed traces",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Filter traces by service name (optional)",
                    },
                    "min_duration": {
                        "type": "string",
                        "description": "Minimum span duration (e.g., '100ms', '1s')",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range (e.g., '1h', '24h')",
                        "default": "1h",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_trace_detail",
            description="Get detailed trace information by trace ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "Trace ID to fetch",
                    },
                },
                "required": ["trace_id"],
            },
        ),
        Tool(
            name="query_loki",
            description="Query Loki for logs using LogQL",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "LogQL query (e.g., '{service=\"order-service\"} | json')",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range (e.g., '1h', '24h', '7d')",
                        "default": "1h",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_datasources",
            description="List all available Grafana datasources",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_dashboards",
            description="List all Grafana dashboards",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_dashboard",
            description="Get Grafana dashboard definition by UID",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_id": {
                        "type": "string",
                        "description": "Dashboard UID",
                    },
                },
                "required": ["dashboard_id"],
            },
        ),
    ]


async def handle_tool_call(name: str, arguments: dict) -> ToolResult:
    """Handle tool calls from Claude"""

    try:
        if name == "query_prometheus":
            result = observability.query_prometheus(
                query=arguments["query"],
                time_range=arguments.get("time_range", "1h"),
            )
        elif name == "query_instant_prometheus":
            result = observability.query_instant_prometheus(
                query=arguments["query"],
            )
        elif name == "query_tempo":
            result = observability.query_tempo(
                service_name=arguments.get("service_name"),
                min_duration=arguments.get("min_duration"),
                time_range=arguments.get("time_range", "1h"),
            )
        elif name == "get_trace_detail":
            result = observability.get_trace_detail(
                trace_id=arguments["trace_id"],
            )
        elif name == "query_loki":
            result = observability.query_loki(
                query=arguments["query"],
                time_range=arguments.get("time_range", "1h"),
            )
        elif name == "get_datasources":
            result = observability.get_datasources()
        elif name == "list_dashboards":
            result = observability.list_dashboards()
        elif name == "get_dashboard":
            result = observability.get_dashboard(
                dashboard_id=arguments["dashboard_id"],
            )
        else:
            result = {"status": "error", "error": f"Unknown tool: {name}"}

        return ToolResult(
            content=[TextContent(type="text", text=json.dumps(result, indent=2))],
            is_error=result.get("status") == "error",
        )

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return ToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"status": "error", "error": str(e)},
                        indent=2,
                    ),
                )
            ],
            is_error=True,
        )


def create_server() -> Server:
    """Create and configure MCP server"""

    server = Server("observability-mcp")

    @server.list_tools()
    async def list_tools():
        return create_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        return await handle_tool_call(name, arguments)

    return server


async def main():
    """Run MCP server"""
    server = create_server()
    async with stdio_server(server) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="observability-mcp",
                server_version="1.0.0",
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
