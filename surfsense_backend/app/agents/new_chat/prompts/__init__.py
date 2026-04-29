"""SurfSense agent prompt fragments.

The prompt is composed at runtime by :mod:`composer` from the markdown
fragments under ``base/``, ``providers/``, ``tools/``, ``examples/``, and
``routing/``. ``system_prompt.py`` is now a thin wrapper that delegates
to :func:`composer.compose_system_prompt`.
"""
