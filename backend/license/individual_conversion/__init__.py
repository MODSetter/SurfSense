"""Individual licenses already sold become Business Solo on the same key (ADR 0080).

Run once, at the switch, by ``scripts/convert_individual_licenses.py``. A
converted license keeps its Stripe subscription untouched, so one that renews
does so at the price it was bought at (ADR 0083).
"""
