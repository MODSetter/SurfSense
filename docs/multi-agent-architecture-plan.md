# Multi-Agent Architecture Plan (Phased)

This document defines a phased migration from the current `single_agent` flow to a multi-agent architecture while keeping rollback simple and immediate.

## Naming

- `single_agent`: current architecture (default at start)
- `shadow_multi_agent_v1`: run multi-agent path in background, return `single_agent` output
- `multi_agent_v1`: multi-agent architecture is the user-facing path

---

## Phase 1 - Parallel Safety Layer

**Goal:** Add safe routing controls with zero behavior change.

### Todo

- [ ] Add mode selector with values: `single_agent`, `shadow_multi_agent_v1`, `multi_agent_v1`
- [ ] Add global kill switch: force all traffic to `single_agent`
- [ ] Add mode resolution priority:
  1. kill switch
  2. request override
  3. system default
- [ ] Keep `single_agent` as default mode
- [ ] Keep frontend stream/output contract unchanged
- [ ] Add telemetry tags:
  - `architecture_mode`
  - `worker_count`
  - `retry_count`
  - `latency_ms`
  - `token_total`
- [ ] Write short rollback runbook

### Exit Criteria

- [ ] Can switch modes in staging
- [ ] Kill switch verified
- [ ] No frontend contract regressions

---

## Phase 2 - Orchestrator Core and Contracts

**Goal:** Build multi-agent control-plane only (planner/router/merge), with strict schemas.

### Todo

- [ ] Implement orchestrator responsibilities:
  - intent detection
  - routing
  - delegation
  - fan-in merge
- [ ] Add budget controls:
  - max workers per turn
  - max parallel workers
  - max turn duration
- [ ] Add loop/stall guard:
  - repeated task signature detection
  - no-progress threshold
- [ ] Define `WorkerTask` schema:
  - `domain`, `goal`, `constraints`, `budget`
- [ ] Define `WorkerResult` schema:
  - `status`, `summary`, `evidence[]`, `artifacts[]`, `needs_human`, `error_class`
- [ ] Add schema validation on send/receive boundaries
- [ ] Add controlled fallback on invalid worker results

### Exit Criteria

- [ ] Orchestrator works end-to-end with mock workers
- [ ] Invalid worker payloads are blocked cleanly

---

## Phase 3 - Pilot Workers (Gmail and Calendar)

**Goal:** Validate multi-agent architecture with two real domains only.

### Todo

- [ ] Create Gmail worker
  - [ ] domain-scoped prompt
  - [ ] domain-only tool loadout
  - [ ] local query rewrite
  - [ ] normalized `WorkerResult`
- [ ] Create Calendar worker
  - [ ] domain-scoped prompt
  - [ ] domain-only tool loadout
  - [ ] local query rewrite/time normalization
  - [ ] normalized `WorkerResult`
- [ ] Enforce no cross-domain tool access
- [ ] Preserve HITL for write actions
- [ ] Add retry policy by `error_class`
- [ ] Add tests for routing, loadout isolation, HITL behavior

### Exit Criteria

- [ ] Gmail and Calendar tasks complete in `multi_agent_v1`
- [ ] No cross-domain tool leakage
- [ ] HITL still enforced for sensitive writes

---

## Phase 4 - Knowledge Base and Evidence Normalization

**Goal:** Isolate KB retrieval and make evidence citation-ready.

### Todo

- [ ] Move KB retrieval behind dedicated worker/stage
- [ ] Reuse current KB retrieval logic, but return compact structured evidence only
- [ ] Define `EvidenceItem` fields:
  - `claim`, `source_type`, `source_ref`, `confidence`, `snippet`
- [ ] Add top-k and output-size controls
- [ ] Add quote-first extraction mode for long contexts
- [ ] Add tests for traceability and bounded payloads

### Exit Criteria

- [ ] Orchestrator consumes compact evidence (no raw KB dumps)
- [ ] Citation refs remain valid and traceable

---

## Phase 5 - Verifier and Citation Gate

**Goal:** Prevent unsupported factual claims in final responses.

### Todo

- [ ] Add verifier stage before final synthesis
- [ ] Enforce claim-to-evidence checks
- [ ] Add conflict handling policy:
  - consistent evidence -> accept
  - conflicting evidence -> label uncertainty or retry
- [ ] Add unsupported-claim policy:
  - remove claim or mark uncertain
- [ ] Add verifier telemetry:
  - supported claims
  - unsupported claims
  - conflicts
- [ ] Support strict gate and warning modes

### Exit Criteria

- [ ] Unsupported factual claims are blocked or clearly annotated
- [ ] Citation precision improves on evaluation set

---

## Phase 6 - Shadow Evaluation and Canary

**Goal:** Ship based on data, not intuition.

### Todo

- [ ] Enable `shadow_multi_agent_v1` for selected traffic
- [ ] Compare metrics vs `single_agent`:
  - success rate
  - citation precision
  - tool-selection accuracy
  - p95 latency
  - tokens/request
  - cost per successful task
- [ ] Define rollout gates and auto-stop thresholds
- [ ] Start canary rollout for `multi_agent_v1`
- [ ] Ramp traffic only if quality and reliability gates pass
- [ ] Keep kill switch live for entire rollout
- [ ] Record go/no-go decision with evidence

### Exit Criteria

- [ ] Clear decision based on measured outcomes
- [ ] Rollback tested successfully during canary

---

## Phase 7 - Domain Expansion and Heavy Tool Reassignment

**Goal:** Scale multi-agent architecture safely across more domains.

### Todo

- [ ] Add domains incrementally (`notion`, `slack`, `jira`, ...)
- [ ] For each new domain enforce:
  - scoped tool loadout
  - local query rewrite
  - contract validation
  - eval plus canary gate
- [ ] Move heavy tools to specialist workers:
  - podcast generation
  - artifact/report generation
  - video presentation
- [ ] Keep orchestrator toolbelt minimal and control-plane focused
- [ ] Regularly prune prompts and tool descriptions

### Exit Criteria

- [ ] New domains onboard without reliability regressions
- [ ] Orchestrator remains lean and stable
- [ ] Cost per successful task stays controlled

---

## Always-On Checklist

- [ ] Keep `single_agent` path healthy until rollout completion
- [ ] Keep one-click rollback available at all times
- [ ] Update observability dashboards every phase
- [ ] Track failure taxonomy and review weekly
- [ ] Validate prompt/tool changes via eval before broad rollout
