# ADR 0005: Schema changes are hand-written Alembic revisions that the API applies at startup

- **Status:** Accepted
- **Date:** 2026-09-03
- **Source:** [Umbrella plan L110–112](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L110-L112), [Connections plan L113–116](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L113-L116)

## Context

The database is one user's `surfsense.db` on their own laptop, with no backup and nobody to inspect it. Alembic's autogenerate cannot see a rename: it emits a drop and an add, which silently deletes the column's data. The hosted backend runs `create_all` on startup, which races its own migrations and breaks releases. The schema as built is in [the data model](../architecture/data-model.md).

## Decision

- SQLAlchemy 2.0 and Alembic, as in the hosted backend. The models are the source of truth.
- Every revision is written and read by a person. Autogenerate is off: [`alembic/env.py`](../../surfsense_local/backend/alembic/env.py) carries no `target_metadata`, so `--autogenerate` cannot be run by accident.
- Alembic is the only schema owner. Nothing calls `create_all`. `upgrade_to_head()` in [`shared/migrations.py`](../../surfsense_local/backend/shared/migrations.py) is the one place in the app allowed to emit DDL.
- The API applies pending revisions at startup, in its lifespan in [`api/main.py`](../../surfsense_local/backend/api/main.py). The workers only read and write rows.
- A test fails when the models and the migrations drift. [`tests/integration/test_migrations.py`](../../surfsense_local/backend/tests/integration/test_migrations.py) builds a database by migration and compares it with `Base.metadata` using Alembic's `compare_metadata`.

## Consequences

- Every schema change costs a hand-written revision. There are twelve, `0001` to `0012`, in [`alembic/versions/`](../../surfsense_local/backend/alembic/versions/).
- Every launch upgrades to head, so a second pass has to be a no-op, and a test holds that. Each revision runs in its own transaction (`transaction_per_migration=True` in `env.py`), and a test checks that a migration that fails leaves nothing behind.
- SQLite cannot alter a CHECK constraint in place, so changing one is written as a table rebuild. Revision `0012` rebuilds `selected_models` this way.
- Tests build their databases through the migrations too, never through `create_all` ([`tests/conftest.py`](../../surfsense_local/backend/tests/conftest.py)).
- The revisions ship inside the frozen API as PyInstaller data, resolved from the package's own `__file__`.
