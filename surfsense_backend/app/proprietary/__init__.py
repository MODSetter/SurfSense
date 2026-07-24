"""SurfSense proprietary packages (non-Apache-2 license boundary).

Everything under ``app.proprietary`` is licensed **separately** from the
Apache-2.0 project root — see ``app/proprietary/LICENSE``. This package holds
the in-house undetectable crawler engine and (future) platform-specific actors
that form the product's moat.

Apache-2.0 code elsewhere in the app may *import from* this package, but code
placed *inside* it is not covered by the repository's Apache-2.0 license.
"""
