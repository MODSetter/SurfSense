# Pipeline diagrams — end-to-end (stateless & stateful paths)

> Visual companion to `00-overview.md`. Shows the whole CI pipeline across Phases 04–07, with the
> **stateless** (Product A) and **stateful** (Product B) paths called out explicitly. Phase refs:
> `04a` Capabilities · `04b` Access · `05a` Timeline · `05b` Intelligence · `06` Triggers · `07` Orchestration.

## 1. Domain map — the two products

```mermaid
flowchart LR
  subgraph FIXED["FIXED · Phases 1-3 (shipped, untouched)"]
    ACQ["Acquisition<br/>proprietary/web_crawler<br/>CrawlOutcome"]
    MET["Metering · 03c<br/>WebCrawlCreditService"]
    ID["Identity / Tenancy<br/>+ API keys"]
    RT["Chat runtime<br/>deepagents · deliverable_wait"]
  end

  subgraph SCOPE["OUR SCOPE · Phase 04 -> 07"]
    CAP["04a Capabilities<br/>typed verbs + registry + job store"]
    ACC["04b Access<br/>chat · REST · MCP doors"]
    INT["05b Intelligence<br/>Tracker · schema · hot loop"]
    TL["05a Timeline<br/>3-store delta state (moat)"]
    TRG["06 Triggers<br/>refresh clock"]
    ORC["07 Orchestration<br/>intelligence_agent subagent"]
  end

  ACQ --> CAP
  MET --> CAP
  CAP --> ACC
  ID --> ACC
  RT --> ORC
  ACC --> ORC
  CAP --> INT
  INT --> TL
  TRG --> INT
  ORC --> CAP
  ORC --> INT
  ORC --> TL

  classDef a fill:#22314f,stroke:#5b7fbf,color:#e6edf7;
  classDef b fill:#1f3a2e,stroke:#4f9d76,color:#e6f7ee;
  class CAP,ACC,INT,TL,TRG,ORC a;
  class ACQ,MET,ID,RT b;
```

- **Product A (stateless):** `04a Capabilities + 04b Access` — call a verb, get data, bill, nothing persists.
- **Product B (stateful):** `05b Intelligence + 05a Timeline` (driven by `06`, fronted by `07`) — a Tracker
  accumulates structured signal; the Timeline is the moat.

## 2. The fork — intent router (the only human-facing decision)

```mermaid
flowchart TD
  U(["User speaks in natural language"]) --> R{"Intent router<br/>(in intelligence_agent prompt, 07)"}
  R -->|"compare / find / what is / pull / right now"| A["ONE-SHOT<br/>Product A · stateless"]
  R -->|"watch / track / notify me / every week / over time"| B["STANDING CONCERN<br/>Product B · stateful"]
  R -->|ambiguous| Q["Ask ONE question:<br/>'just once, or keep watching?'"]
  Q -->|once| A
  Q -->|keep watching| B
  A --> P1["section 3 · Stateless path"]
  B --> P2["section 4 · Stateful path"]
```

Raw verbs are exposed only on REST/MCP (devs/external agents). Humans never name a verb.

## 3. Stateless path (Product A) — end to end

```mermaid
sequenceDiagram
  autonumber
  participant U as User / Dev
  participant D as Door 04b (chat · REST · MCP)
  participant REG as Registry 04a
  participant EX as Verb executor 04a
  participant ACQ as Acquisition / Maps actor
  participant BILL as Billing service (03c)
  participant JOB as Job record (+Celery)

  U->>D: intent (chat) OR raw verb call (REST/MCP)
  D->>D: validate input_schema · authn/authz · meter-gate
  D->>REG: resolve verb
  REG->>EX: same executor (all doors)
  alt fast / small input -> inline
    EX->>ACQ: crawl_url / search / place
    ACQ-->>EX: data
    EX->>BILL: charge billing_unit per success
    EX-->>D: envelope {status: completed, results}
    D-->>U: plain-language answer (chat) / JSON (REST)
  else slow / large input -> job
    EX->>JOB: dispatch, return {status: pending, job_id}
    D-->>U: chat: deliverable_wait polls status<br/>REST/MCP: GET /v1/jobs/{id}
    JOB->>ACQ: work loop
    JOB->>BILL: charge per success
    JOB-->>D: status -> completed (+ results)
    D-->>U: results inline / tracked card
  end
  Note over U,JOB: Nothing persists beyond chat history. No Tracker, no Timeline row.
```

## 4. Stateful path (Product B) — setup, then refresh, then read

### 4a. Setup once — craft & lock the Tracker (05b)

```mermaid
flowchart TD
  S0(["Standing concern detected"]) --> S1["Bind capability + input<br/>(maps.place X / web.scrape Y)"]
  S1 --> S2["Sample fetch · ONE real verb call<br/>(billed)"]
  S2 --> S3["Agent drafts definition from decision + sample:<br/>field_schema · materiality · identity_rule · notable_signals"]
  S3 --> S4{"Human reviews in chat"}
  S4 -->|add field X / tweak| S3
  S4 -->|looks good| S5["LOCK · versioned snapshot<br/>status: draft -> active"]
  S5 --> S6[("Tracker persisted<br/>+ tracked_entities row (05a)")]
```

### 4b. The hot loop — refresh(tracker) (05b → writes 05a)

```mermaid
flowchart TD
  T(["Trigger fires refresh(tracker) · 06"]) --> C1["1 · Crawl: call bound capability (04a)"]
  C1 --> C2{"2 · Content-hash<br/>== stored hash?"}
  C2 -->|identical| STOP["stamp last_checked_at · STOP<br/>(zero LLM cost)"]
  C2 -->|changed / first run| C3["3 · Fill: agent conforms raw -> locked field_schema<br/>(extras -> notable_signals)"]
  C3 --> C4["4 · Diff (code): new record vs entity_current_state -> raw deltas"]
  C4 --> C5{"5 · Judge each delta"}
  C5 -->|numeric / clear rule| C5a["code decides material/noise<br/>(free, reproducible)"]
  C5 -->|ambiguous / notable_signals| C5b["agent decides<br/>(1 LLM call; may read CI context folder)"]
  C5a --> C6{"material?"}
  C5b --> C6
  C6 -->|yes| W["6 · Append entity_changes row<br/>+ overwrite entity_current_state (05a)"]
  C6 -->|no| N["only bump last_checked_at<br/>(no change -> no row)"]
  W --> DONE([done])
  N --> DONE
  STOP --> DONE
```

### 4c. Read / answer — straight from the Timeline (05a)

```mermaid
flowchart LR
  Q(["'Is competitor X pulling ahead?'"]) --> A["intelligence_agent · query_timeline(tracker_id)"]
  A --> TL[("entity_changes + entity_current_state")]
  TL --> ANS["Answer from stored deltas<br/>(NOT re-derived from chat history)"]
```

## 5. Triggers — who calls refresh(tracker) (06)

```mermaid
flowchart LR
  M["Manual<br/>'refresh now' (chat/REST)"] --> RF["refresh(tracker)<br/>headless unit of work · 05b"]
  AG["Agent<br/>calls refresh as a tool"] --> RF
  XC["External cron<br/>POST /v1/trackers/{id}/refresh"] --> RF
  CA["CI automation ACTION<br/>(existing automations)"] --> RF
  RF --> TLW[("writes Timeline · 05a")]

  CA -. "schedule selector" .-> SEL["hardened cron selector"]
  CA -. "run record + idempotency" .-> AR["AutomationRun (PENDING-gate, non-atomic → + per-Tracker lock)"]
  RF -. "on material change" .-> DEL["alert via app/notifications (Zero-synced)"]

  classDef opt fill:#3a2f1f,stroke:#bf975b,color:#f7efe6;
  class CA,SEL,AR opt;
```

CI **core** (`refresh` + Timeline) has **zero** automations dependency — manual/agent/cron all work
standalone. The CI **action** is the *optional* adapter that buys recurrence + audit. **Delivery is not
from automations** (no such path) — alerts on material change ride the separate `app/notifications/`
system; concurrency is guarded by a per-Tracker lock (the automation PENDING-gate is non-atomic).

## 6. The persisted state — Timeline data model (05a)

```mermaid
erDiagram
  TRACKER ||--|| TRACKED_ENTITY : "MVP 1:1 (multi-ready)"
  TRACKED_ENTITY ||--|| ENTITY_CURRENT_STATE : "latest"
  TRACKED_ENTITY ||--o{ ENTITY_CHANGES : "append-only log"

  TRACKER {
    uuid id
    text decision
    json capability_binding
    json definition_locked "field_schema·identity_rule·materiality (versioned)"
    text status "draft|active"
  }
  TRACKED_ENTITY {
    uuid id
    uuid workspace_id
    text entity_key "from identity_rule, unique per tracker"
    ts first_seen_at
  }
  ENTITY_CURRENT_STATE {
    uuid entity_id FK
    json fields "conforms to field_schema"
    text content_hash "powers step-2 pre-check"
    ts last_checked_at
  }
  ENTITY_CHANGES {
    uuid id
    ts captured_at
    json delta "{field:{from,to}}"
    text materiality "material|notable"
    text decided_by "code|agent (provenance)"
    text source_ref
    text note "why material"
  }
```
