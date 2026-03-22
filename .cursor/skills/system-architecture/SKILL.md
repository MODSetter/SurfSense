---
name: system-architecture
description: Design systems with appropriate complexity - no more, no less. Use when the user asks to architect applications, design system boundaries, plan service decomposition, evaluate monolith vs microservices, make scaling decisions, or review structural trade-offs. Applies to new system design, refactoring, and migration planning.
---

# System Architecture

Design real structures with clear boundaries, explicit trade-offs, and appropriate complexity. Match architecture to actual requirements, not imagined future needs.

## Workflow

When the user requests an architecture, follow these steps:

```
Task Progress:
- [ ] Step 1: Clarify constraints
- [ ] Step 2: Identify domains
- [ ] Step 3: Map data flow
- [ ] Step 4: Draw boundaries with rationale
- [ ] Step 5: Run complexity checklist
- [ ] Step 6: Present architecture with trade-offs
```

**Step 1 - Clarify constraints.** Ask about:

| Constraint | Question | Why it matters |
|------------|----------|----------------|
| Scale | What's the real load? (users, requests/sec, data size) | Design for 10x current, not 1000x |
| Team | How many developers? How many teams? | Deployable units ≤ number of teams |
| Lifespan | Prototype? MVP? Long-term product? | Temporary systems need temporary solutions |
| Change vectors | What actually varies? | Abstract only where you have evidence of variation |

**Step 2 - Identify domains.** Group by business capability, not technical layer. Look for things that change for different reasons and at different rates.

**Step 3 - Map data flow.** Trace: where does data enter → how does it transform → where does it exit? Make the flow obvious.

**Step 4 - Draw boundaries.** Every boundary needs a reason: different team, different change rate, different compliance requirement, or different scaling need.

**Step 5 - Run complexity checklist.** Before adding any non-trivial pattern:

```
[ ] Have I tried the simple solution?
[ ] Do I have evidence it's insufficient?
[ ] Can my team operate this?
[ ] Will this still make sense in 6 months?
[ ] Can I explain why this complexity is necessary?
```

If any answer is "no", keep it simple.

**Step 6 - Present the architecture** using the output template below.

## Output Template

```markdown
### System: [Name]

**Constraints**:
- Scale: [current and expected load]
- Team: [size and structure]
- Lifespan: [prototype / MVP / long-term]

**Architecture**:
[Component diagram or description of components and their relationships]

**Data Flow**:
[How data enters → transforms → exits]

**Key Boundaries**:
| Boundary | Reason | Change Rate |
|----------|--------|-------------|
| ... | ... | ... |

**Trade-offs**:
- Chose X over Y because [reason]
- Accepted [limitation] to gain [benefit]

**Complexity Justification**:
- [Each non-trivial pattern] → [why it's needed, with evidence]
```

## Core Principles

1. **Boundaries at real differences.** Separate concerns that change for different reasons and at different rates.
2. **Dependencies flow inward.** Core logic depends on nothing. Infrastructure depends on core.
3. **Follow the data.** Architecture should make data flow obvious.
4. **Design for failure.** Network fails. Databases timeout. Build compensation into the structure.
5. **Design for operations.** You will debug this at 3am. Every request needs a trace. Every error needs context for replay.

For concrete good/bad examples of each principle, see [examples.md](examples.md).

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Microservices for a 3-person team | Well-structured monolith |
| Event sourcing for CRUD | Simple state storage |
| Message queues within the same process | Just call the function |
| Distributed transactions | Redesign to avoid, or accept eventual consistency |
| Repository wrapping an ORM | Use the ORM directly |
| Interfaces with one implementation | Mock at boundaries only |
| AbstractFactoryFactoryBean | Just instantiate the thing |
| DI containers for simple graphs | Constructor injection is enough |
| Clean Architecture for a TODO app | Match layers to actual complexity |
| DDD tactics without strategic design | Aggregates need bounded contexts |
| Hexagonal ports with one adapter | Just call the database |
| CQRS when reads = writes | Add when they diverge |
| "We might swap databases" | You won't; rewrite if you do |
| "Multi-tenant someday" | Build it when you have tenant #2 |
| "Microservices for team scale" | Helps at 50+ engineers, not 4 |

## Success Criteria

Your architecture is right-sized when:

1. **You can draw it** - dependency graph fits on a whiteboard
2. **You can explain it** - new team member understands data flow in 30 minutes
3. **You can change it** - adding a feature touches 1-3 modules, not 10
4. **You can delete it** - removing a component needs no archaeology
5. **You can debug it** - tracing a request takes minutes, not hours
6. **It matches your team** - deployable units ≤ number of teams

## When the Simple Solution Isn't Enough

If the complexity checklist says "yes, scale is real", see [scaling-checklist.md](scaling-checklist.md) for concrete techniques covering caching, async processing, partitioning, horizontal scaling, and multi-region.

## Iterative Architecture

Architecture is discovered, not designed upfront:

1. **Start obvious** - group by domain, not by technical layer
2. **Let hotspots emerge** - monitor which modules change together
3. **Extract when painful** - split only when the current form causes measurable problems
4. **Document decisions** - record why boundaries exist so future you knows what's load-bearing

Every senior engineer has a graveyard of over-engineered systems they regret. Learn from their pain. Build boring systems that work.
