# surfsense_backend

Python 3.12, FastAPI, `uv`. Tests under `tests/`. Root `AGENTS.md` owns organization and TDD.

## Commands

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pytest -m unit
uv run pytest -m integration
```

## Do

- New modules: vertical slice, one responsibility per file. See root `AGENTS.md`.
- FastAPI work: load the `fastapi` skill (repo-root `.agents/skills/fastapi`, not a copy under this tree).
- New behavior: `tdd` skill. Test at public seams.

## Do not

- Do not rewrite existing packages to the new layout unless that is the task.
- Do not run `uvx library-skills` and leave a `.agents/` directory here. The FastAPI skill lives at repo root.
- Do not commit `.env`.
