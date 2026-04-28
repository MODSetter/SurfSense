# Multi-Agent Architecture Phase 1 Runbook

## Scope

This runbook covers mode selection and emergency rollback for:

- `single_agent`
- `shadow_multi_agent_v1`
- `multi_agent_v1`

Phase 1 keeps execution behavior on the current single-agent path while mode wiring and telemetry are introduced.

## Resolution Priority

Mode resolution follows this fixed order:

1. Global kill switch (`FORCE_SINGLE_AGENT`)
2. Request override (`architecture_mode` in chat payload)
3. System default (`AGENT_ARCHITECTURE_MODE`)
4. Safe fallback (`single_agent`)

## Configuration

Set environment values in backend runtime:

- `AGENT_ARCHITECTURE_MODE=single_agent` (default)
- `FORCE_SINGLE_AGENT=FALSE` (default)

Changes require backend restart because config is loaded at process startup.

## Mode Switching

### System default switch

1. Set `AGENT_ARCHITECTURE_MODE` to desired value.
2. Keep `FORCE_SINGLE_AGENT=FALSE`.
3. Restart backend.
4. Verify logs include `[architecture_telemetry]` with expected `architecture_mode`.

### Per-request override

Send optional `architecture_mode` in chat request payload:

- `"single_agent"`
- `"shadow_multi_agent_v1"`
- `"multi_agent_v1"`

If `FORCE_SINGLE_AGENT=TRUE`, request override is ignored by design.

## Emergency Rollback

Use the kill switch:

1. Set `FORCE_SINGLE_AGENT=TRUE`.
2. Restart backend.
3. Verify new requests log `architecture_mode=single_agent`.
4. Keep this state until incident is resolved.

## Verification Checklist

- Mode resolves according to the priority order.
- Kill switch overrides all request/default values.
- Streaming response schema remains unchanged.
- Architecture telemetry is emitted with:
  - `architecture_mode`
  - `orchestrator_used`
  - `worker_count`
  - `retry_count`
  - `latency_ms`
  - `token_total`
