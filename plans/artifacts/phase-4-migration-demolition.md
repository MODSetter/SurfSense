# Phase 4 — Demolition

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§9 removal inventory, §10 legacy deliverables).
**Depends on:** phase 3 complete (no live path creates `Report` rows; all four formats ship through the new pipeline).
**Goal:** delete the legacy system entirely — tools, routes, panel, table, Typst. **There is no data migration** (master spec §10): `reports` is dropped cold and previously generated deliverables become permanently inaccessible. Order is strict: **legacy card + release notes → re-point → delete**.

---

## 1. Legacy handling (§10 of master spec — lands before any deletion PR)

### 1.1 Legacy card

Old chat threads contain `generate_report`/`generate_resume` tool-call parts that something must render forever. Replace their tool UIs with one **static legacy card** component: title from the tool payload + "Generated with the previous artifact system — no longer available. Ask me to regenerate it." No lookup, no data fetch, no panel click-through. Purely presentational.

### 1.2 Release-notes breaking-change warning

The release that drops `reports` carries a prominent breaking-change note: previously generated reports/resumes (all versions) are removed on upgrade; users who want to keep any should export them **before** upgrading (export endpoints exist right up until this version). Documentation only — no export tooling, no prompts in-product (master spec §4.3 boundary: the export decision is the user's).

### 1.3 Re-point surfaces

- Artifacts library → documents query (`GENERATED` file kind / `document_metadata.generated`), replacing `reportsApiService.list`. Old deliverables simply stop appearing.
- Migrated nothing: there are no `migrated_from_report_id` lookups, verification gates, or Typst compiles at upgrade time. The `typst` dependency is removed with zero final use.

---

## 2. Demolition (§9 of master spec — delete, don't flag)

Execute as a sequence of small PRs, each leaving the build green:

### PR 1 — agent layer

- Delete `subagents/builtins/deliverables/tools/{report.py,resume.py}`; deregister from `tools/index.py`, `shared/tools/catalog.py`, prune/tool-name lists, public-chat tool lists.
- Delete `main_agent/skills/builtin/report-writing/`.
- Delete streaming handlers `generate_{report,resume}/` + dead `save_document/` registry name.
- Delete `tests/unit/agents/new_chat/tools/test_resume_page_limits.py`.

### PR 2 — frontend

- Delete `components/report-panel/report-panel.tsx` (including the version-switcher UI — nothing replaces it), `atoms/chat/report-panel.atom.ts`; replace `components/tool-ui/generate-{report,resume}.tsx` with the static legacy card (§1.1). (`pdf-viewer.tsx` already relocated in phase 2.)
- Remove `report`/`resume` artifact kinds + `typst` contentType from `features/chat-artifacts/` — legacy tool parts route to the legacy card, not to artifact collection.
- Delete `lib/apis/reports-api.service.ts`, `contracts/types/reports.types.ts`; remove typst/`pdfOnly` special cases from `ExportMenuItems.tsx`; remove tool icons.

### PR 3 — backend routes & templates

- Delete `routes/reports_routes.py` (including `_get_version_siblings` / `ReportVersionInfo`); remove Typst preview from `public_chat_routes.py`.
- Replace pandoc→typst PDF export in `editor_routes.py` with weasyprint (markdown → HTML → PDF); keep pandoc for docx/html/epub/odt exports of markdown documents.
- Delete `app/templates/report_pdf.typst`, `get_typst_template_path()` from `export_helpers.py`.
- Delete `schemas/reports.py`.

### PR 4 — data & dependencies (last)

- Alembic: drop `reports` table (all rows, including every `report_group_id` sibling version — no data copy); delete `Report` model from `db.py`.
- **Untouched, deliberately:** `document_versions` and `document_revisions`/`folder_revisions` — their lifecycle belongs to the git-native KB plan ([`plans/git-native-kb/`](./git-native-kb/00-umbrella-plan.md)), which deletes them at its Phase 5 cut. This PR neither drops nor depends on them, whether or not that cut has happened yet. See the table fates in master spec §4.1.
- `pyproject.toml`: remove `typst`; remove `pypdf` **only if** `rg pypdf` shows no remaining user; audit `pypandoc` usage stays (document export).
- Remove rendercv references.

---

## 3. Checks

- After each PR: full test suite + `rg -i "generate_report|generate_resume|report_panel|reportsApiService"` returns only changelog/spec hits (plus the legacy-card component, which references the legacy tool names to match message parts).
- After PR 4: `rg -i "typst|rendercv"` → zero hits outside `specs/`; fresh compose deploy passes phases 1–3 exit criteria.
- Old-thread smoke test: a pre-upgrade thread's `generate_report`/`generate_resume` parts render the legacy card with **no network fetch**; nothing errors.

---

## 4. Exit criteria

1. `reports` table dropped; release notes carry the breaking-change warning.
2. Zero code references to `Report`, `typst`, `generate_report`, `generate_resume` outside specs and the legacy-card part matcher.
3. Old threads render legacy cards; artifacts library lists only new-system artifacts.
4. Docker image / dependency footprint reflects the removals (no typst wheel in the backend image).
