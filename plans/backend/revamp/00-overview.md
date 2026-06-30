# Phase 4 → end revamp — Overview & reconciliation (CI pivot · WIP)

> **What this is.** The CI pivot re-architects the old "pipeline" phases (`04`–`07`) into small,
> single-responsibility domains. This file is the map + the reconciliation against the old plans.
> **Scope guardrail:** Phases **1–3 are SHIPPED/FIXED** (rename/DB, proxy/captcha/stealth, crawl
> billing). The revamp is **Phase 4 → end only**. We do **not** touch 1–3.

## The two products

```
PRODUCT A — stateless utility      ① Capabilities + ② Access
  call a verb → get data → bill.  Nothing persists.

PRODUCT B — decision-grounded CI   ③ Intelligence + ④ Timeline  (+ ⑤ Triggers to drive it)
  a Lens accumulates structured signal over time.  The Timeline is the moat.
```

## The domain map

```
            FIXED (Phases 1–3)                        OUR SCOPE (Phase 4 → end)
   ┌─────────────────────────────────┐   ┌──────────────────────────────────────────────┐
   │  Acquisition                     │   │  ① Capabilities   typed verbs over Acquisition │
   │   proprietary/web_crawler        │◄──┤  ② Access         chat · REST · MCP doors      │
   │   CrawlOutcome · billing (03c)   │   │  ③ Intelligence   Lens · schema · hot loop     │
   │                                  │   │  ④ Timeline       3-store delta state (moat)   │
   │                                  │   │  ⑤ Triggers       pluggable refresh clock      │
   │                                  │   │  ⑥ Orchestration  CI-expert subagent + tools   │
   └─────────────────────────────────┘   └──────────────────────────────────────────────┘
        data engine (untouched)             stateless ①② → stateful ③④ , driven by ⑤ , fronted by ⑥
```

| # | Domain | One line | Doc |
|---|--------|----------|-----|
| ① | Capabilities | Acquisition → typed callable verbs (`web.scrape`, `web.discover`, `maps.*`) | `01-capabilities.md` |
| ② | Access | expose verbs to callers, authed + metered (chat / REST / MCP) | `02-access.md` |
| ③ | Intelligence | the Lens, agent-designed locked schema, hot loop (agent judges, code computes) | `03-intelligence.md` |
| ④ | Timeline | durable time-shaped truth; deltas not snapshots; no change → no row | `04-timeline.md` |
| ⑤ | Triggers | when a Lens refreshes; `refresh(lens)` callers; recurrence+delivery = optional CI action on automations | `05-triggers.md` |
| ⑥ | Orchestration | the human-facing CI-expert subagent (intent routing, verb chains, Lens crafting) + its tools | `06-orchestration.md` |
