
# When to Mock

Mock at **system boundaries** only:

* External APIs (payment, email, etc.)
* Databases (sometimes - prefer test DB)
* Time/randomness
* File system (sometimes)

Don't mock:

* Your own classes/modules
* Internal collaborators
* Anything you control

## Designing for Mockability

At system boundaries, design interfaces that are easy to mock:

**1. Use dependency injection**

Pass external dependencies in rather than creating them internally:

```python
import os

# Easy to mock
def process_payment(order, payment_client):
    return payment_client.charge(order.total)

# Hard to mock
def process_payment(order):
    client = StripeClient(os.getenv("STRIPE_KEY"))
    return client.charge(order.total)

```

**2. Prefer SDK-style interfaces over generic fetchers**

Create specific functions for each external operation instead of one generic function with conditional logic:

```python
import requests

# GOOD: Each function is independently mockable
class UserAPI:
    def get_user(self, user_id):
        return requests.get(f"/users/{user_id}")

    def get_orders(self, user_id):
        return requests.get(f"/users/{user_id}/orders")

    def create_order(self, data):
        return requests.post("/orders", json=data)

# BAD: Mocking requires conditional logic inside the mock
class GenericAPI:
    def fetch(self, endpoint, method="GET", data=None):
        return requests.request(method, endpoint, json=data)

```

The SDK approach means:

* Each mock returns one specific shape
* No conditional logic in test setup
* Easier to see which endpoints a test exercises
* Type safety per endpoint