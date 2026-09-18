# Desktop release (`vX.Y.Z`)

One number. Edit `VERSION`, copy it through the tree, tag the same number, push. GitHub’s **Latest** badge stays on legacy `v0.0.40` — never move it.

## Pick the number

`vX.Y.Z` is compared left to right. Newest is the highest, not the last tag you pushed.

| Bump | When | Example |
|------|------|---------|
| **Z** (patch) | Fix | `2.0.0` → `2.0.1` |
| **Y** (minor) | Feature, still compatible | `2.0.1` → `2.1.0` |
| **X** (major) | Breaking | `2.1.0` → `3.0.0` |

`v2.0.1` is newer than `v2.0.0`. `v2.0.0` is newer than `v0.0.40`. A suffix (`-rc.1`) is older than the same number without it.

## Ship it

From the repo root, on the branch you want to release (usually `dev` or `main` after merge). Replace `2.0.1` with this release, and `v2.0.0` with the previous 2.x you shipped.

### 1. Write the new number

No `v` prefix.

```bash
echo -n '2.0.1' > surfsense_local/VERSION
```

### 2. Copy it through the tree

Writes electron, frontend, backend, the website download pin, and the license-email pin.

```bash
surfsense_local/scripts/bump-version.sh
```

### 3. Commit

Include whatever the script changed, including lockfiles.

```bash
git add surfsense_local/VERSION \
  surfsense_local/backend/pyproject.toml surfsense_local/backend/uv.lock \
  surfsense_local/frontend/package.json surfsense_local/electron/package.json \
  surfsense_web/lib/app-release.ts \
  surfsense_backend/app/license/release.py
git commit -m "chore(local): release 2.0.1"
```

### 4. Push the commit

The tag in the next step must point at a commit GitHub already has.

```bash
git push
```

### 5. Open a draft release

Tag must be `v` + the `VERSION` file (CI fails if they disagree). Notes start at the **previous 2.x release** (here `v2.0.0` — the last one you shipped), not GitHub Latest (`v0.0.40`). `--draft` so CI can attach installers before anyone sees it. `--latest=false` so this 2.x does not steal the Latest badge. Creating the draft publishes the tag and starts Desktop Release.

```bash
git tag v2.0.1
gh release create v2.0.1 --draft --generate-notes --notes-start-tag v2.0.0 --latest=false
```

### 6. Publish after CI

Wait until Desktop Release is green on Mac, Windows, and Linux (installers and `stable-*.yml` on the draft). Then:

```bash
gh release edit v2.0.1 --draft=false --latest=false
```

Do not undraft earlier: a published release with missing assets is what the in-app updater would pick up.

## What that starts

A `v*` tag starts `.github/workflows/release-local.yml`. electron-builder uploads Mac / Windows / Linux installers onto the **draft** (`releaseType` defaults to draft). Publish only after those jobs succeed.

| Audience | How they get this build |
|----------|-------------------------|
| Already installed | In-app update. Walks the releases **feed** (not Latest), takes the newest `2.x.y` that has `stable-*.yml`. |
| Website / license email | The **tag pin** in `APP_RELEASE_VERSION`. Needs this bump deployed with web/backend. |

## Dry run (no GitHub Release)

Actions → **Desktop Release** → version `0.0.0-test` (or any `X.Y.Z`) → publish **never**. Unsigned, not a tag, not an update.

## Do not

- Tag `v2.0.1` before `VERSION` is `2.0.1` and the bump script has been committed.
- Push a `v0.*` tag for this app (that line is the legacy desktop).
- Mark a 2.x release as Latest.
- Publish the draft before Mac, Windows, and Linux have uploaded.
- Rely on `/releases/latest` for download links.
