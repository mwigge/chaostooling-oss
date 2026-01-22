"""
JMeter test plan parser for extracting test configuration and endpoints.

Parses .jmx (XML) files to extract:
- HTTP requests (URLs, methods, endpoints)
- Thread groups (users, ramp-up, duration)
- Test plan metadata (name, description)
- Samplers and their configurations
- Service/endpoint patterns for chaos scenario generation
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from xml.etree import ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

logger = logging.getLogger("chaosgeneric.actions.jmeter_parser")


class JMeterTestPlanParser:
    """Parser for JMeter test plan (.jmx) files."""

    def __init__(self, test_plan_path: str):
        """
        Initialize parser with test plan path.

        Args:
            test_plan_path: Path to .jmx test plan file
        """
        self.test_plan_path = Path(test_plan_path)
        if not self.test_plan_path.exists():
            raise FileNotFoundError(f"Test plan not found: {test_plan_path}")

        self.tree: Optional[ET.ElementTree] = None
        self.root: Optional[ET.Element] = None

    def parse(self) -> dict[str, Any]:
        """
        Parse the JMeter test plan and extract structured information.

        Returns:
            Dictionary containing parsed test plan data:
            - test_plan: Metadata (name, description)
            - thread_groups: List of thread group configurations
            - http_requests: List of HTTP request samplers
            - endpoints: Extracted endpoints with service patterns
            - load_config: Load testing configuration
        """
        try:
            self.tree = ET.parse(self.test_plan_path)
            self.root = self.tree.getroot()

            result = {
                "test_plan": self._extract_test_plan_metadata(),
                "thread_groups": self._extract_thread_groups(),
                "http_requests": self._extract_http_requests(),
                "endpoints": self._extract_endpoints(),
                "load_config": self._extract_load_config(),
            }

            logger.info(
                f"Parsed JMeter test plan: {len(result['http_requests'])} HTTP requests, "
                f"{len(result['thread_groups'])} thread groups"
            )

            return result
        except ET.ParseError as e:
            logger.error(f"Failed to parse JMeter test plan XML: {e}")
            raise ValueError(f"Invalid JMeter test plan XML: {e}") from e
        except Exception as e:
            logger.error(f"Failed to parse JMeter test plan: {e}")
            raise

    def _extract_test_plan_metadata(self) -> dict[str, Any]:
        """Extract test plan name and description."""
        test_plan_elem = self.root.find(".//TestPlan")
        if test_plan_elem is None:
            return {"name": "Unknown", "description": ""}

        name = test_plan_elem.get("testname", "Unknown")
        description_elem = test_plan_elem.find(".//stringProp[@name='TestPlan.comments']")
        description = description_elem.text if description_elem is not None else ""

        return {
            "name": name,
            "description": description,
            "filename": self.test_plan_path.name,
        }

    def _extract_thread_groups(self) -> list[dict[str, Any]]:
        """Extract thread group configurations."""
        thread_groups = []
        for tg in self.root.findall(".//ThreadGroup"):
            name = tg.get("testname", "Unknown Thread Group")
            num_threads = self._get_int_prop(tg, "ThreadGroup.num_threads", 1)
            ramp_time = self._get_int_prop(tg, "ThreadGroup.ramp_time", 1)
            duration = self._get_int_prop(tg, "ThreadGroup.duration", 0)
            loops = self._get_int_prop(tg, "LoopController.loops", 1)

            thread_groups.append({
                "name": name,
                "num_threads": num_threads,
                "ramp_time": ramp_time,
                "duration": duration,
                "loops": loops,
            })

        return thread_groups

    def _extract_http_requests(self) -> list[dict[str, Any]]:
        """Extract HTTP request samplers."""
        http_requests = []
        for sampler in self.root.findall(".//HTTPSamplerProxy"):
            name = sampler.get("testname", "Unknown Request")
            domain = self._get_string_prop(sampler, "HTTPSampler.domain", "")
            path = self._get_string_prop(sampler, "HTTPSampler.path", "/")
            method = self._get_string_prop(sampler, "HTTPSampler.method", "GET")
            port = self._get_string_prop(sampler, "HTTPSampler.port", "")
            protocol = self._get_string_prop(sampler, "HTTPSampler.protocol", "http")

            # Build full URL
            url = self._build_url(protocol, domain, port, path)

            http_requests.append({
                "name": name,
                "method": method,
                "url": url,
                "domain": domain,
                "path": path,
                "port": port,
                "protocol": protocol,
            })

        return http_requests

    def _extract_endpoints(self) -> list[dict[str, Any]]:
        """Extract unique endpoints and identify service patterns."""
        endpoints = []
        seen_endpoints = set()

        for request in self._extract_http_requests():
            url = request["url"]
            if url in seen_endpoints:
                continue
            seen_endpoints.add(url)

            parsed = urlparse(url)
            service_name = self._identify_service(parsed.hostname or parsed.netloc)

            endpoints.append({
                "url": url,
                "host": parsed.hostname or parsed.netloc,
                "path": parsed.path,
                "method": request["method"],
                "service_type": service_name,
                "port": parsed.port or (443 if parsed.scheme == "https" else 80),
            })

        return endpoints

    def _extract_load_config(self) -> dict[str, Any]:
        """Extract overall load testing configuration."""
        thread_groups = self._extract_thread_groups()
        if not thread_groups:
            return {
                "total_users": 1,
                "ramp_up_time": 1,
                "duration": 0,
                "estimated_duration": 60,
            }

        total_users = sum(tg["num_threads"] for tg in thread_groups)
        max_ramp_time = max((tg["ramp_time"] for tg in thread_groups), default=1)
        max_duration = max((tg["duration"] for tg in thread_groups), default=0)

        estimated_duration = max_duration if max_duration > 0 else max_ramp_time + 60

        return {
            "total_users": total_users,
            "ramp_up_time": max_ramp_time,
            "duration": max_duration,
            "estimated_duration": estimated_duration,
        }

    def _identify_service(self, hostname: str) -> str:
        """
        Identify service type from hostname or URL pattern.

        Returns service category for chaos scenario selection.
        """
        if not hostname:
            return "unknown"

        hostname_lower = hostname.lower()

        # Database services
        if any(db in hostname_lower for db in ["postgres", "postgresql", "pg"]):
            return "database_postgres"
        if any(db in hostname_lower for db in ["mysql", "mariadb"]):
            return "database_mysql"
        if "mongodb" in hostname_lower or "mongo" in hostname_lower:
            return "database_mongodb"
        if "redis" in hostname_lower:
            return "database_redis"
        if "cassandra" in hostname_lower:
            return "database_cassandra"
        if "mssql" in hostname_lower or "sqlserver" in hostname_lower:
            return "database_mssql"

        # Messaging services
        if "kafka" in hostname_lower:
            return "messaging_kafka"
        if "rabbitmq" in hostname_lower or "rabbit" in hostname_lower:
            return "messaging_rabbitmq"
        if "activemq" in hostname_lower:
            return "messaging_activemq"

        # Application services
        if any(app in hostname_lower for app in ["api", "app", "service", "backend"]):
            return "application"

        # Load balancer
        if any(lb in hostname_lower for lb in ["haproxy", "nginx", "lb", "loadbalancer"]):
            return "load_balancer"

        return "application"

    def _build_url(self, protocol: str, domain: str, port: str, path: str) -> str:
        """Build full URL from components."""
        if not domain:
            return path if path.startswith("/") else f"/{path}"

        port_str = f":{port}" if port and port not in ["80", "443", ""] else ""
        if protocol == "https" and not port_str:
            port_str = ""
        elif protocol == "http" and port == "443":
            protocol = "https"
            port_str = ""

        path = path if path.startswith("/") else f"/{path}"
        return f"{protocol}://{domain}{port_str}{path}"

    def _get_string_prop(self, element: ET.Element, prop_name: str, default: str = "") -> str:
        """Get string property value from element."""
        prop = element.find(f".//stringProp[@name='{prop_name}']")
        return prop.text if prop is not None and prop.text else default

    def _get_int_prop(self, element: ET.Element, prop_name: str, default: int = 0) -> int:
        """Get integer property value from element."""
        prop = element.find(f".//stringProp[@name='{prop_name}']")
        if prop is not None and prop.text:
            try:
                return int(prop.text)
            except ValueError:
                pass
        return default

    def _get_bool_prop(self, element: ET.Element, prop_name: str, default: bool = False) -> bool:
        """Get boolean property value from element."""
        prop = element.find(f".//boolProp[@name='{prop_name}']")
        if prop is not None and prop.text:
            return prop.text.lower() == "true"
        return default

