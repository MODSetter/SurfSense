"""The derived Postgres index of the store, and the queue that drives it.

Deliberately re-exports nothing. :mod:`.converge` reaches into ``app.db``, the
indexing pipeline and the agents middleware, while :mod:`.queue` is a writer's
last step and must stay cheap to import; a convenience re-export here would put
the former on the latter's import path.

Everything in this subpackage is a **driven consumer** of the store (ADR 0002):
it subscribes to revisions one way, and the core never imports it back.
"""
