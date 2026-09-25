# Contributing

Bug fixes and docs are welcome without asking first. A new feature starts with a short design proposal, so we can agree it belongs here before you spend time on a large PR. If you are not sure an idea fits, ask on [Discord](https://discord.gg/ejRNvftDp9) or in [Discussions](https://github.com/MODSetter/SurfSense/discussions) first.

Security: [SECURITY.md](SECURITY.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Find something to work on

- Issues labelled [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) or [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted) are ready to pick up. Comment on one to claim it.
- Every doc in [`docs/architecture/`](docs/architecture/overview.md) ends with a **Known gaps** list: the places where the code does not yet do what the doc says. Each line is a concrete task.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) shows what the maintainers are working on now and next.
- Check [existing issues](https://github.com/MODSetter/SurfSense/issues) and [PRs](https://github.com/MODSetter/SurfSense/pulls) so you do not duplicate work.

## Read before you change anything

[`docs/README.md`](docs/README.md) explains how the docs are organised. For the desktop app, start with [`docs/architecture/overview.md`](docs/architecture/overview.md), the map of `surfsense_local/`, then read the doc for the feature you are touching. Each feature doc links the decision records in [`docs/adr/`](docs/adr/README.md) that explain why it is built the way it is.

## Getting set up

This repo holds four products. Clone it once, then open the README for the product you want to change. You do not need to run the other three.

| If you want to work on | Open |
|------------------------|------|
| Desktop app | [`surfsense_local/README.md`](surfsense_local/README.md) |
| MCP server | [`surfsense_mcp/README.md`](surfsense_mcp/README.md) |
| API / scrapers | [`surfsense_backend/README.md`](surfsense_backend/README.md) |
| Self-host web UI | [`surfsense_web/README.md`](surfsense_web/README.md) |

The web UI needs the API running. Desktop does not. MCP talks to any backend over HTTP.

```bash
git clone https://github.com/<you>/SurfSense.git
cd SurfSense
git checkout dev
git checkout -b fix/short-name
```

We merge through `dev`. Open your PR against that branch.

## How a change gets in

- **Bug fix or small change.** Open a PR against `dev`. If there is an issue, `Fixes #123` links it and closes it on merge.
- **New feature.** First open a PR that adds a proposal, `docs/proposals/<name>.md`, marked `status: proposed`. The header it needs is in [`docs/README.md`](docs/README.md). Once a maintainer accepts it, the code follows in its own PRs. The last of them moves the design into `docs/architecture/`, records any lasting decision in `docs/adr/`, and deletes the proposal.
- **A change to a contract.** Files in [`docs/contracts/`](docs/contracts/README.md) are the interfaces between two parts of the repo, such as the license file the backend issues and the desktop app reads. Changing one needs the agreement of the owners of both sides.
- **Reversing a recorded decision.** An accepted ADR is not rewritten. The change comes with a new ADR that supersedes it ([`docs/adr/README.md`](docs/adr/README.md)).

## Pull requests

Small, focused PRs are easier to review.

- Say what changed, why, and how you tried it.
- If your change alters behaviour that a doc in `docs/architecture/` describes, update the doc in the same PR. If it fixes a Known gap, delete that line.
- Run the tests for what you changed. The commands are in each product's README and in the Testing table in [AGENTS.md](AGENTS.md).
- After editing anything under `docs/` or `plans/`, run `python scripts/check_docs.py`.
- [Allow edits from maintainers](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/allowing-changes-to-a-pull-request-branch-created-from-a-fork) lets us help on the branch.
- New files follow [AGENTS.md](AGENTS.md). Existing packages do not need a layout rewrite unless that is the issue.
- `surfsense_backend/app/proprietary/` is Business Source License 1.1. Ask a maintainer before changing it.
- Keep `.env` and secrets out of the commit.

## Review and merge

CI on the PR should be green. `code-quality.yml` runs the docs checker, file checks and a secrets scan on every PR. Each product lints, scans and tests itself when its files change: `docker-tests.yml` for `surfsense_backend` and `surfsense_web`, including the end-to-end journey, and `desktop-tests.yml` for `surfsense_local`. [CODEOWNERS](.github/CODEOWNERS) asks the maintainer who owns the files you touched to review. One maintainer approval is enough to merge. Merged work lands on `dev` and reaches `main` with the next release.

If you work with a coding agent, [AGENTS.md](AGENTS.md) gives it the same rules, along with the repo's layout and commands.
