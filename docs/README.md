# SurfSense engineering docs

How the desktop app and its hosted services work, why they are built that way, and where to find what is being worked on. Written for maintainers, contributors and coding agents alike. Start with [`architecture/overview.md`](architecture/overview.md).

| Folder | Holds | Changes when |
|---|---|---|
| [`architecture/`](architecture/overview.md) | What is true in the code now, one doc per feature | the behaviour it describes changes |
| [`adr/`](adr/README.md) | One decision per file, with its reasons | a decision is made or superseded |
| [`proposals/`](proposals/plugins/README.md) | Designs for work that is not built yet | the design changes; deleted once the work ships |
| [`contracts/`](contracts/README.md) | Frozen interfaces between trees, with the fixtures their tests read | the owners of both sides approve |
| [`ROADMAP.md`](ROADMAP.md) | The initiatives, grouped Now / Next / Later, each linked to the design it builds on | an initiative starts, finishes or moves |

Business, launch and operations material (pricing, SEO research, runbooks) lives in [`plans/`](../plans/README.md), not here. Setting up a tree to run it is in that tree's README.

## Where status lives

In GitHub issues. Each task is an issue, and `good first issue` and `help wanted` mark the ones that suit an outside contributor. How the issues are grouped by initiative is not decided yet. These docs say how things work, not how far along they are.

Two exceptions: a proposal's `status` field, and the **Known gaps** list at the end of an architecture doc, which names the places where the code does not yet do what the design says. The pull request that closes a gap deletes its line.

## Rules

- Docs describe the code on the branch they live on (`dev`). A release can lag behind them.
- A pull request that changes documented behaviour updates the doc in the same pull request.
- Organize new docs the way root [`AGENTS.md`](../AGENTS.md) asks for code: by feature, one responsibility per file, and a folder once a feature grows sub-parts.
- Link code by path, not by line number; line numbers drift.
- `python scripts/check_docs.py` checks, under `docs/` and `plans/`, that every relative link's target file exists (anchors are not checked), that every table is well formed, and that every proposal declares a known status. It runs as a pre-commit hook, and CI runs it on non-draft pull requests into `dev` and `main`.

## How a feature moves through these folders

1. **Propose.** A pull request adds `proposals/<name>.md`, or `proposals/<name>/README.md` for a design with several parts, opening with front matter:

   ```yaml
   ---
   status: proposed
   tracking: https://github.com/MODSetter/SurfSense/issues/<number>
   code:
     - where/the/work/will/live/
   ---
   ```

   `status` is one of `proposed`, `accepted`, `in-progress`, `deferred` or `withdrawn`. Add `tracking` once the issue exists.

2. **Accept.** Merging the proposal with `status: accepted` accepts it. A maintainer lists it in [`ROADMAP.md`](ROADMAP.md) and opens issues for its work.
3. **Build.** Each implementation pull request links its issue, when there is one. The first one sets `status: in-progress`.
4. **Ship.** The pull request that completes the work folds what is now true into `architecture/`, records its lasting decisions in `adr/`, and deletes the proposal. Git history keeps it.

A bug fix or a small change skips the proposal: open an issue, or a pull request that explains itself.
