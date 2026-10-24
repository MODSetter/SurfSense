# Contributing

This is the `legacy` branch: the self-hosted SurfSense stack, frozen. It takes bug fixes only. New work goes to the desktop app on [`dev`](https://github.com/MODSetter/SurfSense/tree/dev); its contributing guide is there.

Security: [SECURITY.md](SECURITY.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Getting set up

| If you want to fix | Open |
|--------------------|------|
| MCP server | [`surfsense_mcp/README.md`](surfsense_mcp/README.md) |
| API | [`surfsense_backend/README.md`](surfsense_backend/README.md) |
| Web UI | [`surfsense_web/README.md`](surfsense_web/README.md) |

The web UI needs the API running. MCP talks to any backend over HTTP.

```bash
git clone https://github.com/<you>/SurfSense.git
cd SurfSense
git checkout legacy
git checkout -b fix/short-name
```

## Pull requests

Open your PR against `legacy`. If there is an issue, `Fixes #123` links it and closes it on merge.

- Say what changed, why, and how you tried it.
- Run the tests for what you changed. The commands are in each tree's README and in the Testing table in [AGENTS.md](AGENTS.md).
- [Allow edits from maintainers](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/allowing-changes-to-a-pull-request-branch-created-from-a-fork) lets us help on the branch.
- `surfsense_backend/app/proprietary/` is Business Source License 1.1, and only maintainers change it. A pull request from anyone else that touches it is closed.
- Keep `.env` and secrets out of the commit.

## Review and merge

CI on the PR should be green. `code-quality.yml` runs file checks and a secrets scan, and fails a PR from anyone but a maintainer that touches `proprietary/`. `docker-tests.yml` lints, scans and tests `surfsense_backend` and `surfsense_web`, including the end-to-end journey. [CODEOWNERS](.github/CODEOWNERS) asks the maintainer who owns the files you touched to review. One maintainer approval is enough to merge.
