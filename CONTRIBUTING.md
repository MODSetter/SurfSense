# Contributing

Bug fixes and docs are welcome without asking first. For a new feature, open an issue so we can agree it belongs here before you spend time on a large PR.

[`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) is a good place to start. It also helps to check [existing issues](https://github.com/MODSetter/SurfSense/issues) and [PRs](https://github.com/MODSetter/SurfSense/pulls).

Questions: [Discord](https://discord.gg/ejRNvftDp9) or [Discussions](https://github.com/MODSetter/SurfSense/discussions). Security: [SECURITY.md](SECURITY.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

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

## Pull requests

Small, focused PRs are easier to review.

- Say what changed, why, and how you tried it.
- `Fixes #123` links the issue and closes it on merge.
- [Allow edits from maintainers](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/allowing-changes-to-a-pull-request-branch-created-from-a-fork) lets us help on the branch.
- New files follow [AGENTS.md](AGENTS.md). Existing packages do not need a layout rewrite unless that is the issue.
- `surfsense_backend/app/proprietary/` is Business Source License 1.1. Ask a maintainer before changing it.
- Keep `.env` and secrets out of the commit.

CI on the PR should be green. One maintainer review is enough to merge.
