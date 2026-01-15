"""Redis command saturation chaos action."""

import logging
import os
import threading
import time
from typing import Dict, Optional

import redis
from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_command_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    num_threads: int = 20,
    commands_per_thread: int = 1000,
    duration_seconds: int = 60,
    slow_command_threshold_ms: int = 1000,
) -> Dict:
    """Saturate Redis with high volume of commands."""
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    commands_per_thread = (
        int(commands_per_thread)
        if isinstance(commands_per_thread, str)
        else commands_per_thread
    )
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    slow_command_threshold_ms = (
        int(slow_command_threshold_ms)
        if isinstance(slow_command_threshold_ms, str)
        else slow_command_threshold_ms
    )

    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    password = password or os.getenv("REDIS_PASSWORD", None)

    ensure_initialized()
    db_system = "redis"
    metrics = get_metrics_core()
    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler (OpenTelemetry standard)
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.redis.command_saturation")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.redis.command_saturation")

    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_commands = 0
    slow_commands = 0
    errors = 0

    def command_worker(thread_id: int):
        nonlocal total_commands, slow_commands, errors
        r = None
        try:
            with tracer.start_as_current_span(
                f"command_saturation.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system="redis",
                    db_name=None,
                    host=host,
                    port=port,
                    chaos_activity="redis_command_saturation",
                    chaos_action="command_saturation",
                    chaos_operation="command_saturation",
                    chaos_thread_id=thread_id,
                )

                r = redis.Redis(
                    host=host, port=port, password=password, decode_responses=True
                )

                command_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and command_count < commands_per_thread
                ):
                    try:
                        cmd_start = time.time()

                        # Various Redis commands
                        key = f"chaos:sat:{thread_id}:{command_count}"
                        r.set(key, command_count)
                        r.get(key)
                        r.incr(f"chaos:counter:{thread_id}")
                        r.ping()
                        r.info("memory")
                        r.dbsize()

                        cmd_duration_ms = (time.time() - cmd_start) * 1000
                        total_commands += 1
                        command_count += 1

                        get_metric_tags(
                            db_name="redis",
                            db_system="redis",
                            db_operation="saturation_command",
                        )

                        if cmd_duration_ms > slow_command_threshold_ms:
                            slow_commands += 1

                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system, error_type=type(e).__name__
                        )
                        logger.warning(
                            f"Command worker {thread_id} error: {e}",
                            exc_info=True,
                        )

                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(
                f"Command saturation worker {thread_id} failed: {e}",
                exc_info=True,
            )
        finally:
            if r:
                try:
                    r.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.redis.command_saturation") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "command_saturation")
            span.set_attribute("chaos.activity", "redis_command_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "command_saturation")

            logger.info(
                f"Starting Redis command saturation with {num_threads} threads for {duration_seconds}s"
            )

            for i in range(num_threads):
                thread = threading.Thread(target=command_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)

            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)

            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_commands": total_commands,
                "slow_commands": slow_commands,
                "errors": errors,
                "commands_per_second": (
                    total_commands / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.total_commands", total_commands)
            span.set_attribute("chaos.slow_commands", slow_commands)
            span.set_status(StatusCode.OK)

            logger.info(f"Redis command saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(
            f"Redis command saturation failed: {e}",
            exc_info=True,
        )
        flush()
        raise


def stop_command_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
