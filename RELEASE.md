# Releasing legacy

A release publishes `ghcr.io/modsetter/surfsense-backend`, `surfsense-web` and `surfsense-sandbox` from the `legacy` branch. Installs pull `latest`, and Watchtower updates them within a day, so every release reaches users.

## Steps

1. Branch from `legacy` and set `VERSION` to the next patch, `X.Y.Z`.
2. Run `scripts/bump-version.sh`, or `bump-version.ps1` on Windows. It writes the version into `surfsense_web/package.json` and `surfsense_backend/pyproject.toml`, then runs `uv lock`.
   - The `.sh` needs GNU `sed`. On macOS, set those two files by hand and run `uv lock` in `surfsense_backend`.
3. Open a PR: `gh pr create --base legacy`. `docker-build.yml` builds every image and variant without pushing; it, `docker-tests.yml` and `code-quality.yml` must pass.
4. Merge, then tag the merge commit and push the tag:
   ```bash
   git fetch upstream
   git tag legacy-vX.Y.Z upstream/legacy
   git push upstream legacy-vX.Y.Z
   ```
5. The tag's run refuses a tag that does not match `VERSION`, builds again, and pushes `:X.Y.Z`, `:X.Y.Z-cuda`, `:X.Y.Z-cuda126`, `:git-<sha>` and `latest`.
6. Check it: `docker buildx imagetools inspect ghcr.io/modsetter/surfsense-web:X.Y.Z`.

## Rules

- Tags are `legacy-vX.Y.Z`, never `vX.Y.Z`: `v*` tags start the desktop app's release.
- Never move or reuse a published tag. Anyone pinned to `X.Y.Z` must keep the image they have.
- If the tag's run fails before the manifests step, nothing is tagged on GHCR: fix it in a PR, delete the tag (`git push upstream :refs/tags/legacy-vX.Y.Z`), and tag the new merge commit.
- If it fails after some manifests were pushed, release the next patch version instead.
