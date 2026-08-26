"""Gateway telemetry: inbox, outbound, rate-limit, health, and lifecycle metrics."""

from __future__ import annotations

from functools import lru_cache

from app.observability.signals import metrics as m


@lru_cache(maxsize=1)
def _redis_fallback():
    return m.get_meter().create_counter(
        "surfsense.gateway.redis.fallback",
        description="Count of gateway Redis fallback uses.",
    )


@lru_cache(maxsize=1)
def _thread_lock_contention():
    return m.get_meter().create_counter(
        "surfsense.gateway.thread_lock.contention",
        description="Count of gateway per-thread lock contention events.",
    )


@lru_cache(maxsize=1)
def _inbox_writes():
    return m.get_meter().create_counter(
        "surfsense.gateway.inbox.writes",
        description="Count of gateway inbound event inbox writes.",
    )


@lru_cache(maxsize=1)
def _inbox_processed():
    return m.get_meter().create_counter(
        "surfsense.gateway.inbox.processed",
        description="Count of gateway inbound event processing outcomes.",
    )


@lru_cache(maxsize=1)
def _inbound_reconciled():
    return m.get_meter().create_counter(
        "surfsense.gateway.inbound.reconciled",
        description="Count of gateway inbox events re-enqueued by reconciliation.",
    )


@lru_cache(maxsize=1)
def _outbound():
    return m.get_meter().create_counter(
        "surfsense.gateway.outbound",
        description="Count of gateway outbound platform operations.",
    )


@lru_cache(maxsize=1)
def _turn_latency():
    return m.get_meter().create_histogram(
        "surfsense.gateway.turn.latency",
        unit="ms",
        description="Latency of gateway-routed agent turns.",
    )


@lru_cache(maxsize=1)
def _rate_limit_hits():
    return m.get_meter().create_counter(
        "surfsense.gateway.rate_limit.hits",
        description="Count of gateway outbound rate limit waits.",
    )


@lru_cache(maxsize=1)
def _health_check_failures():
    return m.get_meter().create_counter(
        "surfsense.gateway.health_check.failures",
        description="Count of gateway account health-check failures.",
    )


@lru_cache(maxsize=1)
def _auth_invariant_failures():
    return m.get_meter().create_counter(
        "surfsense.gateway.auth_invariant.failures",
        description="Count of gateway authorization invariant failures.",
    )


@lru_cache(maxsize=1)
def _hitl_aborted():
    return m.get_meter().create_counter(
        "surfsense.gateway.hitl.aborted",
        description="Count of gateway turns aborted because HITL is unsupported.",
    )


@lru_cache(maxsize=1)
def _active_bindings():
    return m.get_meter().create_up_down_counter(
        "surfsense.gateway.active_bindings",
        description="Current change in active gateway bindings.",
    )


@lru_cache(maxsize=1)
def _inbox_enqueued():
    return m.get_meter().create_counter(
        "gateway_inbox_enqueued_total",
        description="Count of gateway inbox rows enqueued for worker processing.",
    )


@lru_cache(maxsize=1)
def _inbox_sweep_replayed():
    return m.get_meter().create_counter(
        "gateway_inbox_sweep_replayed_total",
        description="Count of received gateway inbox rows replayed by the sweep.",
    )


@lru_cache(maxsize=1)
def _byo_longpoll_running():
    return m.get_meter().create_up_down_counter(
        "gateway_byo_longpoll_running",
        description="Current change in BYO Telegram long-poll supervisors holding a poll loop.",
    )


@lru_cache(maxsize=1)
def _webhook_parse_errors():
    return m.get_meter().create_counter(
        "gateway_webhook_parse_error_total",
        description="Count of malformed gateway webhook payloads.",
    )


def record_gateway_redis_fallback() -> None:
    m.add(_redis_fallback(), 1, {})


def record_gateway_thread_lock_contention() -> None:
    m.add(_thread_lock_contention(), 1, {})


def record_gateway_inbox_write(*, platform: str, dedup_skipped: bool) -> None:
    m.add(_inbox_writes(), 1, {"platform": platform, "dedup.skipped": bool(dedup_skipped)})


def record_gateway_inbox_processed(*, platform: str, status: str) -> None:
    m.add(_inbox_processed(), 1, {"platform": platform, "status": status})


def record_gateway_inbound_reconciled(*, reason: str) -> None:
    m.add(_inbound_reconciled(), 1, {"reason": reason})


def record_gateway_outbound(*, platform: str, kind: str, status: str) -> None:
    m.add(_outbound(), 1, {"platform": platform, "kind": kind, "status": status})


def record_gateway_turn_latency(duration_ms: float, *, platform: str) -> None:
    m.record(_turn_latency(), duration_ms, {"platform": platform})


def record_gateway_rate_limit_hit(*, bucket: str) -> None:
    m.add(_rate_limit_hits(), 1, {"bucket": bucket})


def record_gateway_health_check_failure(*, platform: str) -> None:
    m.add(_health_check_failures(), 1, {"platform": platform})


def record_gateway_auth_invariant_failure(*, cause: str) -> None:
    m.add(_auth_invariant_failures(), 1, {"cause": cause})


def record_gateway_hitl_aborted(*, platform: str) -> None:
    m.add(_hitl_aborted(), 1, {"platform": platform})


def record_gateway_active_bindings_delta(delta: int, *, platform: str) -> None:
    m.add(_active_bindings(), delta, {"platform": platform})


def record_gateway_inbox_enqueued(*, intake: str, outcome: str) -> None:
    m.add(_inbox_enqueued(), 1, {"intake": intake, "outcome": outcome})


def record_gateway_inbox_sweep_replayed() -> None:
    m.add(_inbox_sweep_replayed(), 1, {})


def record_gateway_byo_longpoll_running_delta(delta: int, *, account_id: int) -> None:
    m.add(_byo_longpoll_running(), delta, {"account_id": account_id})


def record_gateway_webhook_parse_error() -> None:
    m.add(_webhook_parse_errors(), 1, {})
