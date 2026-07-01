# Pipeline diagrams — end-to-end (scraper-APIs-first, stateless)

> Visual companion to `00-umbrella-plan.md`.
> Phase refs: `04` Capabilities · `05` Access · `06` Ongoing-Automation (design deferred) · `07` Orchestration.

## 1. The shape — scraper APIs + a chat agent (no state)

```mermaid
flowchart LR
  subgraph FIXED["FIXED · Phases 1-3 (shipped)"]
    ACQ["Acquisition<br/>crawler · proxy · stealth · captcha"]
    MET["Metering · 03c"]
    ID["Identity / API keys"]
  end

  subgraph SCOPE["OUR SCOPE · Phase 04 -> 07"]
    CAP["04 Capabilities<br/>web.* · maps.*<br/>cleaned, AI-ready output"]
    ACC["05 Access<br/>REST · MCP · chat doors"]
    ORC["07 Orchestration<br/>intelligence_agent"]
    ONG["06 Ongoing-Automation<br/>(keep-watching · DEFERRED)"]
  end

  ACQ --> CAP
  MET --> CAP
  CAP --> ACC
  ID --> ACC
  ACC --> ORC
  ORC -. "standing need" .-> ONG
  ONG -. "re-invokes verbs" .-> CAP

  classDef a fill:#22314f,stroke:#5b7fbf,color:#e6edf7;
  classDef b fill:#1f3a2e,stroke:#4f9d76,color:#e6f7ee;
  classDef d fill:#3a2f1f,stroke:#bf975b,color:#f7efe6;
  class CAP,ACC,ORC a;
  class ACQ,MET,ID b;
  class ONG d;
```

Memory for "what changed" = the chat history.

## 2. Doors — one registry, three surfaces (generated)

```mermaid
flowchart TD
  REG["04 Capability registry<br/>web.scrape · web.discover · maps.search/place/reviews"]
  REG --> R["REST + API keys<br/>(public · OSS self-host · revenue)"]
  REG --> M["MCP server<br/>(external agents · fast-follow)"]
  REG --> C["Chat tools<br/>(in-app agent, 07)"]
  R --> EX["same executor · direct return · 03c billing"]
  M --> EX
  C --> EX
```

## 3. One-shot scrape (the core path) — direct call, no polling

```mermaid
sequenceDiagram
  autonumber
  participant U as User / Dev
  participant D as Door 05 (REST · MCP · chat)
  participant EX as Verb executor 04
  participant ACQ as Acquisition / Maps actor
  participant BILL as Billing (03c)

  U->>D: intent (chat) OR raw verb call (REST/MCP)
  D->>D: validate input_schema · authn/authz · meter-gate
  D->>EX: call executor (same for all doors)
  EX->>ACQ: crawl_url / maps / search
  ACQ-->>EX: cleaned, AI-ready data
  EX->>BILL: charge billing_unit per success
  EX-->>D: results (returned directly)
  D-->>U: plain-language answer (chat) / JSON (REST/MCP)
  Note over U,BILL: Stateless — nothing persists.
```

## 4. Intent fork (in the agent, 07)

```mermaid
flowchart TD
  U(["User speaks in natural language"]) --> R{"Intent router<br/>(intelligence_agent prompt, 07)"}
  R -->|"find / compare / what is / right now"| A["ONE-SHOT<br/>compose verbs, answer (section 3)"]
  R -->|"watch / track / notify me / over time"| B["KEEP-WATCHING<br/>hand to Ongoing-Automation (06)"]
  R -->|ambiguous| Q["Ask ONE question:<br/>'just once, or keep watching?'"]
  Q -->|once| A
  Q -->|keep watching| B
  B -.->|DESIGN DEFERRED| X["06 mechanism TBD<br/>(periodicity · delivery · context limits)"]
```

## 5. "What changed" — chat history is the memory

```mermaid
flowchart LR
  P["Prior tool outputs<br/>(already in chat context)"] --> AG["intelligence_agent"]
  NEW["Fresh verb call (04)"] --> AG
  AG --> ANS["'Here's what's new since last time'<br/>(reasoned from chat history)"]
```

## 6. Ongoing-Automation (06) — intent only, mechanism deferred

```mermaid
flowchart LR
  W["'Keep watching X'"] --> LOOP["Persistent ongoing chat<br/>periodically re-invokes verbs (04)"]
  LOOP --> OUT["results delivered into the session<br/>(write-then-sync / stream)"]
  OUT --> MEM["chat history = memory<br/>agent reports what's new"]
  LOOP -.->|OPEN| Q["periodicity driver? · delivery channel? · context-window limit?"]
  classDef d fill:#3a2f1f,stroke:#bf975b,color:#f7efe6;
  class W,LOOP,OUT,MEM d;
```

> Section 6 is a **placeholder** — the periodic mechanism is designed separately (see `06-ongoing-automation.md`).
