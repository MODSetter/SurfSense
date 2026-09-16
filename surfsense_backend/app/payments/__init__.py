"""Stripe-backed payments: credit packs, auto-reload and webhook delivery.

Knows nothing about licensing. Anything that wants a slice of the Stripe
webhook registers for it via ``app.payments.registry``.
"""
