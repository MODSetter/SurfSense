"""Probe MCP server session lifetime / staleness behavior — read-only.

Goal
----
Empirically answer two questions for our actual third-party MCP servers
(Atlassian, Linear, Slack, ClickUp, Airtable, ...):

1. How expensive is the initial ``initialize`` handshake (``init=`` cost)?
2. How long can a ``ClientSession`` sit idle and still survive a
   subsequent ``list_tools()`` call?

This script informs the design choice between

* per-call sessions (current, ~1s init tax per call),
* per-turn session reuse (LangChain-style, holds a session for the
  duration of a chat turn),
* a long-lived session pool (IBM-style, sessions reused across turns).

The probe is read-only: it only ever calls ``session.list_tools()``,
which is the safest MCP method. No tool calls against user data are
performed.

Usage
-----
Run from the repo root or from ``surfsense_backend/``::

    uv run python -m scripts.probe_mcp_session_lifetime
    uv run python -m scripts.probe_mcp_session_lifetime --quick
    uv run python -m scripts.probe_mcp_session_lifetime --connectors 7,19,20
    uv run python -m scripts.probe_mcp_session_lifetime --intervals 5,30,60,300

Output
------
* Live progress to stderr (``[connector=7 t=+30s] OK 0.142s``).
* Final per-connector table to stdout.
* Raw results JSON to ``./mcp_session_probe_<timestamp>.json``.

The default test reaches 1800s of idle (~30 min). Use ``--quick`` to
stop at 60s for fast iteration. All connectors probe concurrently so
total wall-clock time equals the longest interval, not the sum.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import httpx  # noqa: E402
from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
from sqlalchemy import cast, select  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402

from app.agents.new_chat.tools.mcp_tool import (  # noqa: E402
    _inject_oauth_headers,
    _maybe_refresh_mcp_oauth_token,
)
from app.db import SearchSourceConnector, async_session_maker  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
logger = logging.getLogger("mcp_probe")
logger.setLevel(logging.INFO)


DEFAULT_INTERVALS_SECONDS = [5, 30, 60, 300, 900, 1800]
QUICK_INTERVALS_SECONDS = [5, 30, 60]
PER_CALL_TIMEOUT_SECONDS = 60.0


@dataclass
class CheckpointResult:
    """One ``list_tools()`` call against a long-lived session."""

    idle_seconds_target: int
    elapsed_since_open_seconds: float
    elapsed_since_last_call_seconds: float
    success: bool
    latency_seconds: float | None
    tools_returned: int | None
    error_type: str | None
    error_message: str | None


@dataclass
class ConnectorProbeResult:
    """Per-connector aggregated probe outcome."""

    connector_id: int
    connector_name: str
    connector_type: str
    url: str
    init_latency_seconds: float | None
    first_call_latency_seconds: float | None
    checkpoints: list[CheckpointResult] = field(default_factory=list)
    fatal_error: str | None = None


# ---------------------------------------------------------------------------
# Connector loading + auth
# ---------------------------------------------------------------------------


async def _fetch_connectors(
    connector_ids: list[int] | None,
) -> list[SearchSourceConnector]:
    """Pull every MCP-shaped connector (or only the requested IDs)."""
    async with async_session_maker() as session:
        stmt = select(SearchSourceConnector).filter(
            cast(SearchSourceConnector.config, JSONB).has_key("server_config"),
        )
        if connector_ids:
            stmt = stmt.filter(SearchSourceConnector.id.in_(connector_ids))
        result = await session.execute(stmt)
        connectors = list(result.scalars())

    if connector_ids:
        found_ids = {c.id for c in connectors}
        missing = [cid for cid in connector_ids if cid not in found_ids]
        if missing:
            logger.warning("Requested connector IDs not found: %s", missing)
    return connectors


async def _resolve_authed_server_config(
    connector: SearchSourceConnector,
) -> dict[str, Any] | None:
    """Refresh OAuth (if needed) and return a server_config with auth headers.

    Returns ``None`` if the connector cannot be probed (missing url,
    decrypt failure, no refresh token, etc.).
    """
    cfg = connector.config or {}
    server_config = cfg.get("server_config", {})
    if not isinstance(server_config, dict):
        return None

    if cfg.get("mcp_oauth"):
        async with async_session_maker() as session:
            attached = await session.get(SearchSourceConnector, connector.id)
            if attached is None:
                return None
            refreshed = await _maybe_refresh_mcp_oauth_token(
                session,
                attached,
                attached.config or {},
                server_config,
            )
            attached_cfg = attached.config or {}
        server_config = _inject_oauth_headers(attached_cfg, refreshed)
        if server_config is None:
            return None
    return server_config


# ---------------------------------------------------------------------------
# The actual probe
# ---------------------------------------------------------------------------


def _classify_error(exc: BaseException) -> tuple[str, str]:
    """Return ``(short_label, human_message)`` for a failed call."""
    name = type(exc).__name__
    msg = str(exc) or repr(exc)
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout", f"call exceeded {PER_CALL_TIMEOUT_SECONDS}s"
    if "404" in msg or "Not Found" in msg or "session" in msg.lower():
        return "session_expired", msg
    if "401" in msg or "Unauthorized" in msg:
        return "auth_401", msg
    if "ClosedResourceError" in name or "Closed" in name:
        return "stream_closed", msg
    if "Connection" in name or "ConnectError" in name:
        return "connection_error", msg
    return name, msg


async def _probe_one_connector(
    connector: SearchSourceConnector,
    intervals: list[int],
) -> ConnectorProbeResult:
    """Open a single long-lived session, call ``list_tools`` at each interval."""
    connector_type = (
        connector.connector_type.value
        if hasattr(connector.connector_type, "value")
        else str(connector.connector_type)
    )
    server_config = await _resolve_authed_server_config(connector)
    if server_config is None:
        return ConnectorProbeResult(
            connector_id=connector.id,
            connector_name=connector.name,
            connector_type=connector_type,
            url="(unresolved)",
            init_latency_seconds=None,
            first_call_latency_seconds=None,
            fatal_error="failed_to_resolve_server_config",
        )

    url = server_config.get("url")
    headers = server_config.get("headers", {})
    if not url:
        return ConnectorProbeResult(
            connector_id=connector.id,
            connector_name=connector.name,
            connector_type=connector_type,
            url="(missing)",
            init_latency_seconds=None,
            first_call_latency_seconds=None,
            fatal_error="missing_url",
        )

    transport = server_config.get("transport", "streamable-http")
    if transport not in ("streamable-http", "http", "sse"):
        return ConnectorProbeResult(
            connector_id=connector.id,
            connector_name=connector.name,
            connector_type=connector_type,
            url=url,
            init_latency_seconds=None,
            first_call_latency_seconds=None,
            fatal_error=f"unsupported_transport:{transport}",
        )

    result = ConnectorProbeResult(
        connector_id=connector.id,
        connector_name=connector.name,
        connector_type=connector_type,
        url=url,
        init_latency_seconds=None,
        first_call_latency_seconds=None,
    )

    open_started = time.perf_counter()
    last_call_at: float | None = None

    # Manually drive the context-manager protocol so the session lives
    # across our sleep intervals. ``streamable_http_client`` spawns a
    # background task for the SSE receive loop; ``ClientSession`` spawns
    # another for request multiplexing. We must close them in reverse order.
    http_client = httpx.AsyncClient(headers=headers, timeout=PER_CALL_TIMEOUT_SECONDS)
    transport_cm = None
    session_cm = None
    session = None
    try:
        transport_cm = streamable_http_client(url, http_client=http_client)
        read, write, _ = await transport_cm.__aenter__()
        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()

        init_start = time.perf_counter()
        await asyncio.wait_for(session.initialize(), timeout=PER_CALL_TIMEOUT_SECONDS)
        result.init_latency_seconds = time.perf_counter() - init_start
        logger.info(
            "[connector=%s name=%r] init=%.3fs",
            connector.id,
            connector.name,
            result.init_latency_seconds,
        )

        first_call_start = time.perf_counter()
        first_response = await asyncio.wait_for(
            session.list_tools(), timeout=PER_CALL_TIMEOUT_SECONDS
        )
        result.first_call_latency_seconds = time.perf_counter() - first_call_start
        last_call_at = time.perf_counter()
        logger.info(
            "[connector=%s name=%r] first_call=%.3fs tools=%d",
            connector.id,
            connector.name,
            result.first_call_latency_seconds,
            len(first_response.tools),
        )

        for interval in intervals:
            target_elapsed = open_started + (
                result.init_latency_seconds + result.first_call_latency_seconds + interval
            )
            sleep_for = max(0.0, target_elapsed - time.perf_counter())
            await asyncio.sleep(sleep_for)

            call_start = time.perf_counter()
            elapsed_since_open = call_start - open_started
            elapsed_since_last = call_start - (last_call_at or call_start)
            try:
                response = await asyncio.wait_for(
                    session.list_tools(), timeout=PER_CALL_TIMEOUT_SECONDS
                )
                latency = time.perf_counter() - call_start
                last_call_at = time.perf_counter()
                checkpoint = CheckpointResult(
                    idle_seconds_target=interval,
                    elapsed_since_open_seconds=round(elapsed_since_open, 3),
                    elapsed_since_last_call_seconds=round(elapsed_since_last, 3),
                    success=True,
                    latency_seconds=round(latency, 3),
                    tools_returned=len(response.tools),
                    error_type=None,
                    error_message=None,
                )
                logger.info(
                    "[connector=%s t=+%ds] OK %.3fs (tools=%d)",
                    connector.id,
                    interval,
                    latency,
                    len(response.tools),
                )
                result.checkpoints.append(checkpoint)
            except Exception as exc:  # noqa: BLE001
                label, msg = _classify_error(exc)
                latency_at_failure = time.perf_counter() - call_start
                checkpoint = CheckpointResult(
                    idle_seconds_target=interval,
                    elapsed_since_open_seconds=round(elapsed_since_open, 3),
                    elapsed_since_last_call_seconds=round(elapsed_since_last, 3),
                    success=False,
                    latency_seconds=round(latency_at_failure, 3),
                    tools_returned=None,
                    error_type=label,
                    error_message=msg[:300],
                )
                logger.warning(
                    "[connector=%s t=+%ds] FAILED %s after %.3fs: %s",
                    connector.id,
                    interval,
                    label,
                    latency_at_failure,
                    msg[:200],
                )
                result.checkpoints.append(checkpoint)
                # Session is presumed dead — further checkpoints would all
                # fail the same way and just waste wall time.
                break

    except Exception as exc:  # noqa: BLE001
        label, msg = _classify_error(exc)
        result.fatal_error = f"{label}: {msg[:200]}"
        logger.exception(
            "[connector=%s] fatal during open/init: %s",
            connector.id,
            exc,
        )
    finally:
        if session_cm is not None:
            try:
                await session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        if transport_cm is not None:
            try:
                await transport_cm.__aexit__(None, None, None)
            except Exception:
                pass
        try:
            await http_client.aclose()
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _render_table(results: list[ConnectorProbeResult]) -> str:
    """Pretty-print a per-connector summary suitable for the terminal."""
    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("MCP Session Lifetime Probe Results")
    lines.append("=" * 100)

    for result in results:
        lines.append("")
        lines.append(
            f"Connector {result.connector_id} | {result.connector_type} | "
            f"{result.connector_name!r}"
        )
        lines.append(f"  url: {result.url}")
        if result.fatal_error:
            lines.append(f"  FATAL: {result.fatal_error}")
            continue
        lines.append(
            f"  init handshake: "
            f"{result.init_latency_seconds:.3f}s"
            if result.init_latency_seconds is not None
            else "  init handshake: (failed)"
        )
        lines.append(
            f"  first list_tools (cold): "
            f"{result.first_call_latency_seconds:.3f}s"
            if result.first_call_latency_seconds is not None
            else "  first list_tools: (failed)"
        )
        if not result.checkpoints:
            lines.append("  (no idle checkpoints recorded)")
            continue
        lines.append(
            f"  {'idle_s':>8} | {'since_last':>10} | {'outcome':>16} | "
            f"{'latency':>9} | {'tools':>5}"
        )
        for cp in result.checkpoints:
            outcome = "OK" if cp.success else (cp.error_type or "FAIL")
            latency = f"{cp.latency_seconds:.3f}s" if cp.latency_seconds is not None else "-"
            tools = str(cp.tools_returned) if cp.tools_returned is not None else "-"
            lines.append(
                f"  {cp.idle_seconds_target:>8} | "
                f"{cp.elapsed_since_last_call_seconds:>10.1f} | "
                f"{outcome:>16} | "
                f"{latency:>9} | "
                f"{tools:>5}"
            )

    lines.append("")
    lines.append("=" * 100)
    lines.append("Summary")
    lines.append("=" * 100)
    survived: dict[int, list[int]] = {}
    for result in results:
        for cp in result.checkpoints:
            if cp.success:
                survived.setdefault(cp.idle_seconds_target, []).append(
                    result.connector_id
                )
    if survived:
        for interval in sorted(survived):
            ids = sorted(survived[interval])
            lines.append(
                f"  Idle {interval:>5}s: {len(ids)}/{len(results)} connectors "
                f"survived ({ids})"
            )
    else:
        lines.append("  (no successful checkpoints)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe MCP server session lifetime (read-only)",
    )
    parser.add_argument(
        "--connectors",
        type=_parse_int_list,
        default=None,
        help="Comma-separated connector IDs to probe. Default: all MCP connectors.",
    )
    parser.add_argument(
        "--intervals",
        type=_parse_int_list,
        default=None,
        help="Comma-separated idle intervals in seconds. "
        f"Default: {DEFAULT_INTERVALS_SECONDS}",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=f"Short run (intervals={QUICK_INTERVALS_SECONDS}) for fast iteration.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path for the raw JSON results.",
    )
    return parser.parse_args()


async def _async_main() -> int:
    args = _parse_args()
    if args.intervals is not None:
        intervals = args.intervals
    elif args.quick:
        intervals = QUICK_INTERVALS_SECONDS
    else:
        intervals = DEFAULT_INTERVALS_SECONDS

    longest = max(intervals) if intervals else 0
    logger.info(
        "Probing intervals=%s (longest=%ds, ~%dmin total wall time)",
        intervals,
        longest,
        (longest + 30) // 60,
    )

    connectors = await _fetch_connectors(args.connectors)
    if not connectors:
        logger.error("No MCP connectors found to probe.")
        return 2
    logger.info(
        "Probing %d connector(s): %s",
        len(connectors),
        [f"{c.id}:{c.name}" for c in connectors],
    )

    started_at = time.time()
    results = await asyncio.gather(
        *[_probe_one_connector(c, intervals) for c in connectors],
        return_exceptions=False,
    )
    elapsed = time.time() - started_at
    logger.info("All probes complete in %.1fs", elapsed)

    table = _render_table(results)
    print(table)

    output_path = (
        args.output
        or f"mcp_session_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "started_at": datetime.fromtimestamp(started_at).isoformat(),
                "elapsed_seconds": round(elapsed, 1),
                "intervals_tested": intervals,
                "results": [asdict(r) for r in results],
            },
            fp,
            indent=2,
        )
    logger.info("Raw results saved to %s", output_path)
    return 0


def main() -> None:
    try:
        exit_code = asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
