# Desktop release (`vX.Y.Z`)

One number. Edit `VERSION`, copy it through the tree, merge `dev` into `main`, and tag that merge with the same number. Publishing moves GitHub’s **Latest** badge to the new release; pass `--latest` anyway, so it does not rest on GitHub’s default.

Publishing a release makes it Latest, and the legacy 0.0.x desktop reads `latest*.yml` from whatever Latest names. The `legacy-update-bridge` job puts v0.0.40's manifests on every release so those clients keep landing on v0.0.40 and its `/sunset` redirect. **That job has to be green before you undraft**, or every legacy update check 404s. So does `release-extras`, which runs after it: the apt repository and `SHA256SUMS` are read off Latest too.

## Pick the number

`vX.Y.Z` is compared left to right. Newest is the highest, not the last tag you pushed.

| Bump | When | Example |
|------|------|---------|
| **Z** (patch) | Fix | `2.0.0` → `2.0.1` |
| **Y** (minor) | Feature, still compatible | `2.0.1` → `2.1.0` |
| **X** (major) | Breaking | `2.1.0` → `3.0.0` |

`v2.0.1` is newer than `v2.0.0`. `v2.0.0` is newer than `v0.0.40`. A suffix (`-rc.1`) is older than the same number without it.

## Ship it

From the repo root, on `dev`. A release is `dev` merged into `main` by pull request, with the tag on that merge. Replace `2.3.0` with this release and `v2.2.0` with the previous 2.x you shipped.

Before you start, check both signing credentials are current. Apple refuses notarization with a 403 until the account holder accepts a new developer agreement, as on 3 Oct 2026, and every release run checks for that before building, as does a weekly run of [`notarization-credentials.yml`](../.github/workflows/notarization-credentials.yml) ([#2224](https://github.com/MODSetter/SurfSense/issues/2224)). Windows signing needs the Azure client secret behind `AZURE_CLIENT_SECRET`, whose expiry Entra ID shows; only a tag's build uses it.

Merge the changelog entry into `dev` before the bump, as a `docs(changelog): vX.Y.Z` pull request adding `www/content/changelog/<date>.mdx` with `version: "X.Y.Z"`. The website builds from `main`, so an entry merged after the release pull request stays off surfsense.com/changelog until another reaches `main`.

### 1. Write the new number

No `v` prefix.

```bash
echo -n '2.3.0' > surfsense_local/VERSION
```

In Windows PowerShell, write it as ASCII. PowerShell 5.1's `>` and `-Encoding utf8` both add a byte-order mark, and the script then rejects the version it reads.

```powershell
Set-Content surfsense_local/VERSION '2.3.0' -NoNewline -Encoding ascii
```

### 2. Copy it through the tree

Writes electron, frontend, backend, the website download pin, and the license-email pin, then refreshes `uv.lock` when `uv` is on the `PATH`. It needs bash and a Python that runs.

```bash
surfsense_local/scripts/bump-version.sh
```

On Windows, call Git Bash by its path. A plain `bash` in PowerShell is usually `C:\Windows\System32\bash.exe`, which starts WSL.

```powershell
& "C:\Program Files\Git\bin\bash.exe" surfsense_local/scripts/bump-version.sh
```

### 3. Commit and push to `dev`

Include whatever the script changed, including lockfiles.

```bash
git add surfsense_local/VERSION \
  surfsense_local/backend/pyproject.toml surfsense_local/backend/uv.lock \
  surfsense_local/frontend/package.json surfsense_local/electron/package.json \
  www/features/downloads/app-release.ts \
  backend/license/release.py
git commit -m "chore(local): release 2.3.0"
git push origin dev
```

### 4. Merge `dev` into `main`

Open the release pull request, read its checks, and merge it. Security Scan runs detect-secrets over every file the release changes since `main`, so it flags pinned sha256 hashes and test fixtures; read each finding ([#2225](https://github.com/MODSetter/SurfSense/issues/2225)).

Before merging, re-check every cell of the root README's format table against `dev` ([06-repo-readme](../plans/community-local/seo/06-repo-readme.md#the-readme-since-9-oct-2026)). A cell that changes, changes in every `README.<locale>.md` too, in a commit on `dev` before the merge.

```bash
gh pr create --base main --head dev --title "[Local|Release] Release desktop 2.3.0"
```

### 5. Tag the merge and open a draft release

Tag must be `v` + the `VERSION` file (CI fails if they disagree), on the commit the merge made on `main`. Pushing the tag starts Desktop Release. Push it yourself: `--verify-tag` makes `gh` stop when the remote lacks the tag, rather than create one on the default branch's head. Notes start at the **previous 2.x release** — the last one you shipped. `--draft` so CI can attach installers before anyone sees it.

```bash
git fetch origin main
git tag v2.3.0 "$(gh pr view <pr> --json mergeCommit --jq .mergeCommit.oid)"
git push origin v2.3.0
gh release create v2.3.0 --verify-tag --draft --generate-notes --notes-start-tag v2.2.0
```

### 6. Watch the build

2.2.0's took 45 minutes. Wait until the `build` legs are green on Mac, Windows, and Linux (installers, `SurfSense.rpm` among them, and `stable-*.yml` on the draft), `legacy-update-bridge` has attached `latest.yml`, `latest-mac.yml` and `latest-linux.yml`, **and** `release-extras` has run after both. Watch those jobs, not the run: the run stays in progress until the `snap` job ends, up to 90 minutes later. Check all six manifests are there:

```bash
gh run list --workflow release-local.yml --limit 1
gh run view <run-id> --json jobs \
  --jq '.jobs[] | select(.name | test("^(build|legacy-update-bridge|release-extras)")) | "\(.name) \(.status) \(.conclusion)"'
gh release view v2.3.0 --json assets --jq '.assets[].name' | grep -E '^(stable|latest)'
```

`gh run watch <run-id>` also works, but it follows the `snap` job too: stop it once `release-extras` is green.

`release-extras` attaches `install.sh` and `install.ps1` from `surfsense_local/packaging/install/`. When the `APT_GPG_PRIVATE_KEY` secret is set, it then builds the apt repository from the `SurfSense.deb` already on the draft ([`build-apt-repo.sh`](packaging/apt/build-apt-repo.sh)): `Packages`, `Packages.gz`, `Release`, `InRelease`, `Release.gpg` and `surfsense-archive-keyring.gpg`. Last, it writes `SHA256SUMS` from GitHub's digest of every other asset ([`write-sha256sums.mjs`](packaging/checksums/write-sha256sums.mjs)). Check they are there, and that `SHA256SUMS` matches what you download:

```bash
gh release view v2.3.0 --json assets --jq '.assets[].name' \
  | grep -E '^(install\.(sh|ps1)|Packages(\.gz)?|Release(\.gpg)?|InRelease|surfsense-archive-keyring\.gpg|SHA256SUMS)$'
gh release download v2.3.0 --pattern SHA256SUMS --pattern 'install.*' --dir sums
(cd sums && sha256sum --check --ignore-missing SHA256SUMS)
```

Without the key, `release-extras` leaves a notice only while Latest carries no `InRelease`. Once Latest serves the apt repository it fails instead, because apt users' `apt update` reads the files off Latest and a release without them would break it. Every release's `Packages` names the same `latest/download/SurfSense.deb`, so an `apt upgrade` whose lists were read before a publish and whose deb is fetched after it fails with a size or hash mismatch until the user runs `apt update` again. Anything uploaded to the draft after `release-extras`, such as a re-run build leg, leaves `SHA256SUMS` stale; re-run `release-extras` last.

The `snap` job is informational. Nothing waits on it, and its failure leaves the run green. On a tag with `SNAPCRAFT_STORE_CREDENTIALS` set, it uploads `SurfSense.snap` to the Snap Store's candidate channel; the snap never goes on the GitHub release. Do not wait for it before publishing.

### 7. Add Known issues to the draft

The generated notes list pull requests. Above them, under `## Known issues`, write what a user must know before updating: what the first start needs, what going back to the previous version takes, and the bugs the release still has. 2.2.0's named the free disk its first start needs for the database snapshot, the hand restore of `~/.surfsense/backups/0023-0027.db` that going back to 2.1.0 takes, and the chats an interrupted import misses (#1958).

```bash
gh release view v2.3.0 --json body --jq .body > notes.md
# write "## Known issues" above "## What's Changed"
gh release edit v2.3.0 --notes-file notes.md
```

### 8. Try it over the previous version (optional)

The updater reads only published releases, so no installed app is offered the draft. Before publishing, install the draft's installer over the previous version on a machine that holds that version's library, and check the library opens and, when the release migrates the database, that the snapshot lands in `~/.surfsense/backups/`. Once published, Check now in Settings › About on a machine still on the previous version shows the update itself. From a previous version newer than 2.2.3, the `updater` lines of the session log show the differential download: `To download:` is about a tenth of `Full:` on Windows, and `fallback to full download` means it failed and the whole installer came instead; `not 206` in that line means something on the network ignored the range requests ([updates](../docs/architecture/updates.md#update-size)).

```bash
gh release download v2.3.0 --pattern 'SurfSense-Setup.exe'
```

### 9. Publish

```bash
gh release edit v2.3.0 --draft=false --latest
```

Do not undraft earlier. Undrafting makes this release Latest, and both updaters read their manifest off it the moment it is: a missing `stable-*.yml` strands 2.x clients, a missing `latest*.yml` strands every legacy 0.0.x client.

Undrafting with your own `gh` login also starts [`release-channels.yml`](../.github/workflows/release-channels.yml). An undraft made with `GITHUB_TOKEN` would start no workflow, so keep this step by hand. Check it went green:

```bash
gh run list --workflow release-channels.yml --limit 1
```

## What that starts

A `v[1-9]*` tag starts `.github/workflows/release-local.yml`; a `v0.*` tag never does. electron-builder uploads Mac / Windows / Linux installers onto the **draft** (`releaseType` defaults to draft), `legacy-update-bridge` adds v0.0.40's manifests, and `release-extras` adds the install scripts, the apt repository and `SHA256SUMS`. Publish only after all of those succeed. The `snap` job runs beside them and holds none of them up.

| Audience | How they get this build |
|----------|-------------------------|
| Already installed | In-app update on the `stable` channel. Shipped 2.0.x clients set `allowPrerelease`, so they walk the releases **feed** and take its newest entry; that entry is this release. |
| Legacy 0.0.x desktop | Not this build. `/releases/latest` names this release, but its `latest*.yml` answers v0.0.40 — see `legacy-update-bridge`. |
| Website, READMEs, license email | The **tag pin** in `APP_RELEASE_VERSION`, through the site's `/downloads/<platform>` redirect ([updates](../docs/architecture/updates.md#download-links)). Needs this bump deployed with web/backend. Until you publish, the redirect sends them to Latest, the previous release. A license email already sent stays on its own tag. |

Publishing starts `release-channels.yml`, for the package managers that do not watch GitHub for themselves. Each job leaves a notice and does nothing when its secret is empty.

| Job | What it does |
|-----|--------------|
| `winget` | Opens a pull request on microsoft/winget-pkgs updating `SurfSense.SurfSense` to `SurfSense-Setup.exe` ([winget-releaser](https://github.com/vedantmgoyal9/winget-releaser)). It only updates a package winget already lists. |
| `aur` | Renders `surfsense-bin`'s PKGBUILD with `surfsense_local/packaging/channels/render.mjs`, checksums from the release's asset digests, and pushes it to the AUR as `Update to X.Y.Z`. |
| `snap` | Waits up to an hour for the Snap Store's candidate channel to hold this version, then promotes it to stable. It never promotes an older candidate. |

Homebrew (BrewTestBot) and Scoop (Excavator) find the release on their own schedule, so no job bumps them. apt offers it on a user's next `apt update`, since their source follows Latest. To run the channels again, for instance after the snap job finished late or a secret was added:

```bash
gh workflow run release-channels.yml -f tag=v2.3.0
```

### Secrets

| Secret | Used by | Where it comes from |
|--------|---------|---------------------|
| `APT_GPG_PRIVATE_KEY` | `release-extras` | The armored secret key that signs the apt repository. Make it once, with no expiry, because an expired key fails every user's `apt update`: `gpg --quick-gen-key 'SurfSense apt repository' ed25519 sign never`, then `gpg --armor --export-secret-keys <fingerprint>`. Keep an offline copy. Users trust only this key, so replacing it means every user fetches the keyring again. |
| `APT_GPG_PASSPHRASE` | `release-extras` | That key's passphrase. Leave it unset for a key without one. |
| `SNAPCRAFT_STORE_CREDENTIALS` | `snap` in both workflows | Register the name once with `snapcraft register surfsense-local`, then `snapcraft export-login --snaps=surfsense-local --acls package_access,package_push,package_update,package_release -`. The login expires (`--expires` sets when); export a new one before it does. |
| `WINGET_TOKEN` | `winget` | A classic personal access token with `public_repo` and `workflow` scopes from a dedicated bot account that owns a fork of microsoft/winget-pkgs and has no access to MODSetter's repositories, since the action hands the token to code it fetches unpinned (`cargo-binstall@main` and the latest komac). Set the repository variable `WINGET_FORK_USER` to the bot's login; without it the action looks for the fork under the repository owner. Submit the first version by hand, with `wingetcreate new` or `komac new`. |
| `AUR_SSH_PRIVATE_KEY` | `aur` | The private half of an SSH key whose public half is on the AUR account that maintains `surfsense-bin` (aur.archlinux.org, My Account, SSH Public Key). |

## Dry run (no GitHub Release)

Actions → **Desktop Release** → version `0.0.0-test` (or any `X.Y.Z`) → publish **never**, or:

```bash
gh workflow run release-local.yml --ref dev -f version=0.0.0-test -f publish=never
```

Not a tag, not an update: the installers stay on the run as artifacts, and neither `legacy-update-bridge` nor `release-extras` runs. The `snap` job still builds the snap, as the `surfsense-local-snap` artifact, and uploads it nowhere. It is not unsigned. macOS is signed and notarized, because the Apple secrets reach every run in this repository. Windows is unsigned: the macOS certificate reaches only the macOS runner, and Azure Trusted Signing is used only by a tag. Linux signs nothing. A fork has none of these secrets, so its run signs nothing.

## Do not

- Tag `v2.3.0` before `VERSION` is `2.3.0` and the bump script has been committed.
- Tag `dev`, or any commit but the release pull request's merge on `main`.
- Push a `v0.*` tag for this app (that line is the legacy desktop).
- Publish the draft before Mac, Windows and Linux have uploaded, and before `legacy-update-bridge` and `release-extras` are green.
- Upload to the draft after `release-extras` without re-running it, or `SHA256SUMS` no longer matches the release.
- Undraft with `GITHUB_TOKEN`, from a workflow or a bot: `release-channels.yml` would never start.
- Delete `legacy-update-bridge` while 0.0.x clients are still checking in. Watch `SurfSense-Setup-0.0.40.exe.blockmap` on the v0.0.40 release: while it climbs, legacy installs are still migrating.
- Rely on `/releases/latest` for download links. It names the right release now, but the site, the READMEs and the license email go through `/downloads/<platform>`, which names exact asset filenames, so they stay in lockstep with `APP_RELEASE_VERSION` instead, and fall back to Latest only while that tag is unpublished.
- Rename an installer. `/downloads/<platform>` builds every URL from the tag and the fixed names in `www/features/downloads/app-release.ts`, so a renamed file breaks every link already sent, mails included.
