---
name: system-architecture
description: Design systems with appropriate complexity—no more, no less. Use this skill when the user asks to architect applications, design system boundaries, or make structural decisions. Generates pragmatic architectures that solve real problems without premature abstraction.
---

This skill guides creation of system architectures that match actual requirements, not imagined future needs. Design real structures with clear boundaries, explicit trade-offs, and appropriate complexity.

The user provides architecture requirements: a system to design, a scaling challenge, or structural decisions to make. They may include context about team size, expected load, or existing constraints.

<architecture_design_thinking>
## Design Thinking

Before designing, understand the actual constraints:

- **Scale**: What's the real load? 100 users? 10,000? 10 million? Design for 10x current, not 1000x.
- **Team**: How many developers? Microservices for a 3-person team is organizational overhead, not architecture.
- **Lifespan**: Prototype? MVP? Long-term product? Temporary systems need temporary solutions.
- **Change vectors**: What actually varies? Abstract only where you have evidence of variation.

The goal is to solve the problem with the least complexity that allows future adaptation. Every abstraction, every boundary, every pattern has a cost. Pay only for what you need.

Then design systems that are:

- Appropriate to actual scale and team size
- Easy to understand and modify
- Explicit about trade-offs and constraints
- Deletable—components can be removed without archaeology
</architecture_design_thinking>

<architecture_guidelines>
## Architecture Guidelines

### Draw Boundaries at Real Differences
Separate concerns that change for different reasons and at different rates.

<example_good title="Meaningful boundary">
# Users and Billing are separate bounded contexts
# - Different teams own them
# - Different change cadences (users: weekly, billing: quarterly)
# - Different compliance requirements

src/
  users/           # User management domain
    models.py
    services.py
    api.py
  billing/         # Billing domain
    models.py
    services.py
    api.py
  shared/          # Truly shared utilities
    auth.py
</example_good>

<example_bad title="Ceremony without purpose">
# UserService → UserRepository → UserRepositoryImpl
# ...when you'll never swap the database

src/
  interfaces/
    IUserRepository.py      # One implementation exists
  repositories/
    UserRepositoryImpl.py   # Wraps SQLAlchemy, which is already a repository
  services/
    UserService.py          # Just calls the repository
</example_bad>

### Make Dependencies Explicit and Directional
Core logic depends on nothing. Infrastructure depends on core.

<example_good title="Clear dependency direction">
# Dependency flows inward: infrastructure → application → domain

domain/           # Pure business logic, no imports from outer layers
  order.py        # Order entity with business rules

application/      # Use cases, orchestrates domain
  place_order.py  # Imports from domain/, not infrastructure/

infrastructure/   # External concerns
  postgres.py     # Implements persistence, imports from application/
  stripe.py       # Implements payments
</example_good>

### Follow the Data
Architecture should make data flow obvious. Where does it enter? How does it transform? Where does it exit?

<example_good title="Obvious data flow">
Request → Validate → Transform → Store → Respond

# Each step is a clear function/module:
api/routes.py        # Request enters
validators.py        # Validation
transformers.py      # Business logic transformation
repositories.py      # Storage
serializers.py       # Response shaping
</example_good>

### Design for Failure
Network fails. Databases timeout. Services crash. Build this into the structure.

<example_good title="Failure-aware design">
class OrderService:
    def place_order(self, order: Order) -> Result:
        # Explicit failure handling at boundaries
        inventory = self.inventory.reserve(order.items)
        if inventory.failed:
            return Result.failure("Items unavailable", retry=False)

        payment = self.payments.charge(order.total)
        if payment.failed:
            self.inventory.release(inventory.reservation_id)  # Compensate
            return Result.failure("Payment failed", retry=True)

        return Result.success(order)
</example_good>

### Design for Operations
You will debug this at 3am. Can you trace a request? Can you replay a failure?

<example_good title="Observable architecture">
# Every request gets a correlation ID
# Every service logs with that ID
# Every error includes context for reproduction

@trace
def handle_request(request):
    log.info("Processing", request_id=request.id, user=request.user_id)
    try:
        result = process(request)
        log.info("Completed", request_id=request.id, result=result.status)
        return result
    except Exception as e:
        log.error("Failed", request_id=request.id, error=str(e),
                  context=request.to_dict())  # Full context for replay
        raise
</example_good>
</architecture_guidelines>

<architecture_anti_patterns>
## Patterns to Avoid

Avoid premature distribution:
- Microservices before you've earned them → Start with a well-structured monolith
- Event sourcing for CRUD apps → Use simple state storage
- Message queues between functions in the same process → Just call the function
- Distributed transactions → Redesign to avoid them or accept eventual consistency

Avoid abstraction theater:
- Repository wrapping an ORM → The ORM is already a repository
- Interfaces with one implementation "for testing" → Mock at boundaries, not everywhere
- AbstractFactoryFactoryBean → Just instantiate the thing
- DI containers for simple object graphs → Constructor injection is enough

Avoid cargo cult patterns:
- "Clean architecture" with 7 layers for a TODO app → Match layers to actual complexity
- DDD tactical patterns without strategic design → Aggregates need bounded contexts
- Hexagonal ports when you have one adapter → Just call the database
- CQRS when reads and writes are identical → Add complexity when reads/writes diverge

Avoid future-proofing:
- "We might need to swap databases" → You won't; if you do, you'll rewrite anyway
- "This could become multi-tenant" → Build it when you have the second tenant
- "Microservices will help us scale the team" → They help at 50+ engineers, not 4
</architecture_anti_patterns>

<architecture_success_criteria>
## Success Criteria

Your architecture is right-sized when:

1. **You can draw it**: The dependency graph fits on a whiteboard. If it doesn't, simplify.
2. **You can explain it**: A new team member understands data flow in under 30 minutes.
3. **You can change it**: Adding a feature touches 1-3 modules, not 10.
4. **You can delete it**: Removing a component doesn't require archaeology to find hidden dependencies.
5. **You can debug it**: Tracing a request from entry to exit takes minutes, not hours.
6. **It matches your team**: Number of deployable units ≤ number of teams.
</architecture_success_criteria>

<architecture_complexity_decisions>
## When to Add Complexity

Add complexity when you have:
- **Measured evidence**: Profiling shows the bottleneck, not intuition
- **Proven need**: The simpler solution has failed or is failing
- **Operational capacity**: The team can deploy, monitor, and debug the added complexity
- **Clear benefit**: The gain exceeds the cognitive and operational cost

A checklist before adding architectural complexity:

```
[ ] Have I tried the simple solution?
[ ] Do I have evidence it's insufficient?
[ ] Can my team operate this?
[ ] Will this still make sense in 6 months?
[ ] Can I explain why this complexity is necessary?
```

If any answer is "no", keep it simple.
</architecture_complexity_decisions>

<architecture_iteration>
## Iterative Architecture

Architecture is discovered, not designed upfront. For complex systems:

1. **Start with the obvious structure**: Group by domain, not by technical layer
2. **Let hotspots emerge**: Monitor which modules change together—they might belong together
3. **Extract when painful**: Only split a module when its current form causes measurable problems
4. **Document decisions**: Record why boundaries exist so future you knows what's load-bearing
</architecture_iteration>

Every senior engineer has a graveyard of over-engineered systems they regret. Learn from their pain. Build boring systems that work.
