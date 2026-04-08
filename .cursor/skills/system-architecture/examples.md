# Architecture Examples

Concrete good/bad examples for each core principle in SKILL.md.

---

## Boundaries at Real Differences

**Good** - Meaningful boundary:
```
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
```

**Bad** - Ceremony without purpose:
```
# UserService → UserRepository → UserRepositoryImpl
# ...when you'll never swap the database

src/
  interfaces/
    IUserRepository.py      # One implementation exists
  repositories/
    UserRepositoryImpl.py   # Wraps SQLAlchemy, which is already a repository
  services/
    UserService.py          # Just calls the repository
```

---

## Dependencies Flow Inward

**Good** - Clear dependency direction:
```
# Dependency flows inward: infrastructure → application → domain

domain/           # Pure business logic, no imports from outer layers
  order.py        # Order entity with business rules

application/      # Use cases, orchestrates domain
  place_order.py  # Imports from domain/, not infrastructure/

infrastructure/   # External concerns
  postgres.py     # Implements persistence, imports from application/
  stripe.py       # Implements payments
```

---

## Follow the Data

**Good** - Obvious data flow:
```
Request → Validate → Transform → Store → Respond

# Each step is a clear function/module:
api/routes.py        # Request enters
validators.py        # Validation
transformers.py      # Business logic transformation
repositories.py      # Storage
serializers.py       # Response shaping
```

---

## Design for Failure

**Good** - Failure-aware design with compensation:
```python
class OrderService:
    def place_order(self, order: Order) -> Result:
        inventory = self.inventory.reserve(order.items)
        if inventory.failed:
            return Result.failure("Items unavailable", retry=False)

        payment = self.payments.charge(order.total)
        if payment.failed:
            self.inventory.release(inventory.reservation_id)  # Compensate
            return Result.failure("Payment failed", retry=True)

        return Result.success(order)
```

---

## Design for Operations

**Good** - Observable architecture:
```python
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
```

Key elements:
- Every request gets a correlation ID
- Every service logs with that ID
- Every error includes full context for reproduction
