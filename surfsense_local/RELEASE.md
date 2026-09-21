# Desktop release (`vX.Y.Z`)

One number. Edit `VERSION`, copy it through the tree, tag the same number, push. GitHub’s **Latest** badge moves to each new 2.x release, which is the default — you do not pass a flag for it.

Publishing a release makes it Latest, and the legacy 0.0.x desktop reads `latest*.yml` from whatever Latest names. The `legacy-update-bridge` job puts v0.0.40's manifests on every release so those clients keep landing on v0.0.40 and its `/sunset` redirect. **That job has to be green before you undraft**, or every legacy update check 404s.

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

Writes electron, frontend, backend, the website download pin, and the license-email pin. On Windows run it through `bash`, not PowerShell. Do **not** reach for `scripts/bump-version.*` at the repo root — that is the hosted stack's own version line and it will not touch this app.

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

Tag must be `v` + the `VERSION` file (CI fails if they disagree). Notes start at the **previous 2.x release** — the last one you shipped. `--draft` so CI can attach installers before anyone sees it. Pushing the tag starts Desktop Release.

Push the tag yourself rather than letting `gh` create it. `gh release create` puts a missing tag on the **default branch** head, which is the wrong commit whenever you release from `dev`.

```bash
git tag v2.0.1
git push origin v2.0.1
gh release create v2.0.1 --draft --generate-notes --notes-start-tag v2.0.0
```

### 6. Publish after CI

Wait until Desktop Release is green on Mac, Windows, and Linux (installers and `stable-*.yml` on the draft) **and** `legacy-update-bridge` has attached `latest.yml`, `latest-mac.yml` and `latest-linux.yml`. Check all six manifests are there:

```bash
gh release view v2.0.1 --json assets --jq '.assets[].name' | grep -E '^(stable|latest)'
gh release edit v2.0.1 --draft=false
```

Do not undraft earlier. Undrafting makes this release Latest, and both updaters read their manifest off it the moment it is: a missing `stable-*.yml` strands 2.x clients, a missing `latest*.yml` strands every legacy 0.0.x client.

## What that starts

A `v*` tag starts `.github/workflows/release-local.yml`. electron-builder uploads Mac / Windows / Linux installers onto the **draft** (`releaseType` defaults to draft), and `legacy-update-bridge` adds v0.0.40's manifests. Publish only after all of those succeed.

| Audience | How they get this build |
|----------|-------------------------|
| Already installed | In-app update on the `stable` channel. Shipped 2.0.x clients set `allowPrerelease`, so they walk the releases **feed** and take its newest entry; that entry is this release. |
| Legacy 0.0.x desktop | Not this build. `/releases/latest` names this release, but its `latest*.yml` answers v0.0.40 — see `legacy-update-bridge`. |
| Website / license email | The **tag pin** in `APP_RELEASE_VERSION`. Needs this bump deployed with web/backend. |

## Dry run (no GitHub Release)

Actions → **Desktop Release** → version `0.0.0-test` (or any `X.Y.Z`) → publish **never**. Unsigned, not a tag, not an update.

## Do not

- Tag `v2.0.1` before `VERSION` is `2.0.1` and the bump script has been committed.
- Push a `v0.*` tag for this app (that line is the legacy desktop).
- Publish the draft before Mac, Windows and Linux have uploaded, and before `legacy-update-bridge` is green.
- Delete `legacy-update-bridge` while 0.0.x clients are still checking in. Watch `SurfSense-Setup-0.0.40.exe.blockmap` on the v0.0.40 release: while it climbs, legacy installs are still migrating.
- Rely on `/releases/latest` for download links. It names the right release now, but the site and the license email reference exact asset filenames, so they stay in lockstep with `APP_RELEASE_VERSION` instead.
