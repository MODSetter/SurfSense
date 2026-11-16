# Install channels

Where the desktop app is offered besides its GitHub release, what keeps each channel current on its own, and what a maintainer does once per channel. Releasing, and the secrets each job reads, are in [RELEASE.md](../RELEASE.md#secrets). Nothing here submits anything: every first submission below is made by a maintainer, under their own account.

| Channel | Name | Ships | After the first version |
|---|---|---|---|
| [Homebrew cask](#homebrew) | `surfsense` | the arm64 dmg on macOS, the x86_64 AppImage on Linux | BrewTestBot bumps it |
| [winget](#winget) | `SurfSense.SurfSense` | `SurfSense-Setup.exe` | `winget` job of [release-channels.yml](../../.github/workflows/release-channels.yml) |
| [Scoop Extras](#scoop) | `surfsense` | `SurfSense-Setup.exe`, unpacked | Excavator bumps it |
| [AUR](#aur) | `surfsense-bin` | `SurfSense.deb`, repackaged | `aur` job of release-channels.yml |
| [Snap Store](#snap-store) | `surfsense-local` | the snap from release-local.yml | `snap` jobs of release-local.yml (candidate) and release-channels.yml (stable) |
| [apt repository](#apt-repository) | `surfsense-local-electron` | `SurfSense.deb` | `release-extras` job of release-local.yml |
| [Install scripts](#install-scripts) | `install.sh`, `install.ps1` | the platform's installer | `release-extras` uploads them |
| [Microsoft Store](#microsoft-store) | SurfSense | `SurfSense-Setup.exe` by URL | a new submission by hand, per release |

Scoop, the AUR, the snap and the apt repository update the app themselves, so the app hands updates to them: it reads `resources/install-channel` (written by the Scoop manifest and the PKGBUILD) or recognises the snap and the apt source, then never updates itself and says "Updates come from …" in Settings ([install-channel.ts](../electron/src/main/install-channel/install-channel.ts)). Submit Scoop and the AUR only from the first release that carries that code; 2.2.3 does not, and would update itself out from under them. Homebrew and winget are not in that list: they upgrade the app the ordinary way, and its own updater, off by default, may also run.

Flathub is out of scope: its rules forbid AI-written or AI-assisted manifests. Softpedia refuses apps with LLM-written code, and Softonic, FileHippo and Chip wrap downloads in their own installers; leave them out.

## Rendering the files

Homebrew, winget, Scoop and the AUR take files generated from the release:

```bash
node surfsense_local/packaging/channels/render.mjs <homebrew|winget|scoop|aur> --version X.Y.Z --out <dir>
```

It reads the release from GitHub's API (sending `GH_TOKEN` when set), or from `--assets release.json` as `gh api repos/MODSetter/SurfSense/releases/tags/vX.Y.Z` prints it. Every checksum is GitHub's digest of the asset, so no installer is downloaded. It refuses a draft, a prerelease, a release tagged other than `vX.Y.Z`, and any asset that is missing or has no digest, and then writes nothing. The tests run with `pnpm test` in `surfsense_local/electron`, or `node --test "surfsense_local/packaging/channels/*.test.mjs"`.

| Channel | Writes |
|---|---|
| `homebrew` | `surfsense.rb` |
| `winget` | `manifests/s/SurfSense/SurfSense/X.Y.Z/SurfSense.SurfSense.{installer,locale.en-US,}.yaml` |
| `scoop` | `surfsense.json` |
| `aur` | `PKGBUILD` and `.SRCINFO` |

## Homebrew

A pull request to [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask) adding `Casks/s/surfsense.rb` ([Adding software](https://docs.brew.sh/Adding-Software-to-Homebrew), [Cask Cookbook](https://docs.brew.sh/Cask-Cookbook)). A project may submit its own cask once it has 90 forks, 90 watchers or 225 stars; SurfSense has all three.

Their rules for this pull request, from its template and [Responsible AI Usage](https://docs.brew.sh/Responsible-AI-Usage):

- Disclose in the description that the cask was generated with AI help (name the tool and model) and how you checked it.
- No commit may credit AI. The commit message is cask style, `surfsense X.Y.Z (new cask)`, not a conventional commit.
- Answer review comments yourself, without AI. A non-maintainer may have one AI-assisted pull request open at a time.
- The app must pass Gatekeeper; casks that fail it are disabled. The dmg is notarized.

On an Apple Silicon Mac:

```bash
node surfsense_local/packaging/channels/render.mjs homebrew --version X.Y.Z --out cask
brew tap --force homebrew/cask
cp cask/surfsense.rb "$(brew --repository homebrew/cask)/Casks/s/surfsense.rb"
HOMEBREW_NO_INSTALL_FROM_API=1 brew install --cask surfsense   # open the app once, then quit it
brew generate-zap surfsense                                     # compare with the cask's zap
brew uninstall --cask surfsense
brew audit --new --cask surfsense
brew audit --cask --online surfsense
brew style --fix --cask surfsense
brew lgtm --online
```

Then commit on a branch of your fork, push, and open the pull request with the template filled in. If you can, also `brew install --cask surfsense` on an x86_64 Linux with Homebrew.

Choices a reviewer may ask about:

- **`auto_updates true` sits inside `on_macos` only.** With it, `brew upgrade` still upgrades the Mac app whenever its bundle is older than the cask, which it is while the in-app updater is off (the default), and skips it when the app already updated itself. On Linux the AppImage has no bundle version to compare, so a top-level `auto_updates` would make plain `brew upgrade` skip it for good. [unsloth](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/u/unsloth.rb), with the same arm64 Mac and x86_64 Linux shape, does the same.
- **`livecheck` uses `strategy :github_latest`** because tags are pushed while the release is still a draft, and published later.
- **`zap` trashes `~/.surfsense`**, the app's data folder (its userData lives in `~/.surfsense/electron`), with the user's indexed documents and downloaded models. `--zap` moves it to the Trash. If a reviewer counts it as files created by the user, take it out and add a caveat naming it. `~/Library/Application Support/SurfSense` belongs to the legacy 0.0.x app and is never zapped.
- **`depends_on macos: :ventura`** matches the bundle's `LSMinimumSystemVersion` of 13.0; `brew audit` compares the two.

## winget

The first version goes in by hand to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) ([contributing](https://github.com/microsoft/winget-pkgs/blob/master/CONTRIBUTING.md)). A first-time contributor signs the Microsoft CLA when the bot asks on the pull request.

On Windows:

```powershell
node surfsense_local/packaging/channels/render.mjs winget --version X.Y.Z --out winget
winget validate --manifest winget\manifests\s\SurfSense\SurfSense\X.Y.Z
winget settings --enable LocalManifestFiles     # once, as administrator
winget install --manifest winget\manifests\s\SurfSense\SurfSense\X.Y.Z
winget list SurfSense.SurfSense                 # must show it, matched by ProductCode
winget uninstall SurfSense.SurfSense
```

Copy the folder to the same path in a fork of winget-pkgs and open the pull request as `New package: SurfSense.SurfSense version X.Y.Z` (or `wingetcreate submit` it).

After that, the `winget` job opens each version's pull request with [winget-releaser](https://github.com/vedantmgoyal9/winget-releaser). It needs a dedicated bot account that owns a fork of winget-pkgs and has no access to MODSetter's repositories: its PAT is `WINGET_TOKEN`, and the repository variable `WINGET_FORK_USER` names it (the job falls back to the repository owner).

What the manifests say, and why:

- `nullsoft`, `Scope: user`, x64: electron-builder's one-click per-user NSIS. winget passes `/S` for nullsoft itself, and `Upgrade: --updated` tells the installer it is an upgrade, as Obsidian's and LM Studio's manifests do.
- `ProductCode` is the uninstall key, `9a7516bd-33e2-5724-857c-bd937d1ea1f8` without braces, the UUID v5 of the appId. winget matches the installed app by it, so there is no `AppsAndFeaturesEntries`, as in Obsidian's and LM Studio's.
- No `RequireExplicitUpgrade`, because the in-app updater is off by default, and no `ExpectedReturnCodes`: electron-builder's exit code 2 means the old version failed to uninstall, not that the app is running.

## Scoop

[ScoopInstaller/Extras](https://github.com/ScoopInstaller/Extras) takes a pull request only after a Package Request issue.

1. Open a [Package Request](https://github.com/ScoopInstaller/Extras/issues/new?template=package-request.yml): name `SurfSense`, description the summary below, homepage `https://www.surfsense.com`, download link the release's `SurfSense-Setup.exe`, and the repository's stars and forks for popularity (the bar is 100 stars or 50 forks).
2. Render and try it on Windows:

   ```powershell
   node surfsense_local/packaging/channels/render.mjs scoop --version X.Y.Z --out scoop
   scoop install .\scoop\surfsense.json
   ```

   Open the app: Settings must say updates come from Scoop, and `~\scoop\apps\surfsense\current\resources\install-channel` must hold `scoop`. Then `scoop uninstall surfsense`.
3. In a clone of Extras, add it as `bucket/surfsense.json` and check the autoupdate: `.\bin\checkver.ps1 surfsense -ForceUpdate` must report the hash found in GitHub mode, not by downloading.
4. Open the pull request as `surfsense: Add version X.Y.Z`, with `Closes #<issue>`.

After that, Excavator bumps it from `checkver` and `autoupdate`. With no `hash` block, Scoop reads the asset's GitHub digest (Scoop's `github` hash mode, since August 2025), so it never downloads the 1.2 GB installer to hash it. Installing unpacks the NSIS and then its `app-64.7z`, about twice the app's size in temporary disk. The data stays in `~/.surfsense`, outside the app folder, so nothing is persisted.

## AUR

The AUR has no review, and `-bin` packages are allowed.

1. Make an account on [aur.archlinux.org](https://aur.archlinux.org) and add an SSH public key under My Account.
2. Set its private key as the `AUR_SSH_PRIVATE_KEY` secret ([RELEASE.md](../RELEASE.md#secrets)), then `gh workflow run release-channels.yml -f tag=vX.Y.Z`. The `aur` job clones the still-empty `surfsense-bin` and its first push creates it.
3. Or push it by hand: `git clone ssh://aur@aur.archlinux.org/surfsense-bin.git`, copy in the rendered `PKGBUILD` and `.SRCINFO`, commit and push.
4. On Arch, check it builds and installs: `makepkg -si` in the rendered folder (a 1.35 GB download and about 7 GB of scratch space), then `namcap PKGBUILD` and `namcap surfsense-bin-*.pkg.tar.zst`.

The PKGBUILD unpacks the deb's `data.tar.*`, writes `aur` to `/opt/SurfSense/resources/install-channel`, deletes `resources/app-update.yml` and `resources/package-type`, links `/usr/bin/surfsense-local` and `/usr/bin/surfsense`, and links the bundled third-party notices into `/usr/share/licenses/surfsense-bin/`. Its depends are the deb's under Arch's names (`gcc-libs` carries libgomp for llama.cpp) plus `alsa-lib`. `!strip` keeps the frozen backend and the model runtimes as built. Its `# Maintainer:` line says `SurfSense <noreply@surfsense.app>`; change it in [`aur.mjs`](channels/aur.mjs) to the AUR account's.

## Snap Store

The build and upload are automated; the name and the login are not.

1. With an Ubuntu One account: `snapcraft login`, then `snapcraft register surfsense-local`.
2. Export a login limited to that snap and set it as `SNAPCRAFT_STORE_CREDENTIALS` ([RELEASE.md](../RELEASE.md#secrets) has the command). It expires; export a new one before it does.
3. Fill the listing on [snapcraft.io](https://snapcraft.io/surfsense-local/listing): title, summary, description, icon and screenshots.
4. `audio-record` is not connected on install, so speech to text needs `snap connect surfsense-local:audio-record` until the store grants auto-connection; ask for it in the forum's store-requests category.

The store has reported trouble with uploads near 1.5 GB; the snap is at that edge.

## apt repository

`release-extras` builds a signed flat repository from the release's `SurfSense.deb` once `APT_GPG_PRIVATE_KEY` is set ([RELEASE.md](../RELEASE.md#secrets) says how to make the key). Users add it with `install.sh`, or by hand:

```bash
sudo curl -fsSLo /usr/share/keyrings/surfsense-archive-keyring.gpg \
  https://github.com/MODSetter/SurfSense/releases/latest/download/surfsense-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/surfsense-archive-keyring.gpg] https://github.com/MODSetter/SurfSense/releases/latest/download/ ./" \
  | sudo tee /etc/apt/sources.list.d/surfsense.list
sudo apt update && sudo apt install surfsense-local-electron
```

The app treats a deb as apt's only when `/etc/apt/sources.list.d/surfsense.list` exists, so document no other file name. Once anyone uses it, every release must carry the apt files.

## Install scripts

`curl -fsSL https://www.surfsense.com/install.sh | sh` and `irm https://www.surfsense.com/install.ps1 | iex` redirect to the copies on Latest ([install-script-redirects.ts](../../surfsense_web/lib/install-script-redirects.ts)); the scripts are in [`install/`](install/). The redirects go live with the site's next deploy. Nothing to submit.

## Microsoft Store

By hand, in Partner Center, as an EXE app.

1. Open a **Company** developer account: free since 7 May 2026, verified with a D-U-N-S number or business documents in 2 to 5 days. An Individual account cannot be converted later.
2. Reserve the name SurfSense and create an EXE or MSI app.
3. Packages: the release's own URL, `https://github.com/MODSetter/SurfSense/releases/download/vX.Y.Z/SurfSense-Setup.exe`, never a `/latest/` one, since the file behind the URL must not change. Architecture x64, silent switch `/S`, language en-US.
4. Listing: the description below, privacy policy `https://www.surfsense.com/privacy`.
5. Notes for certification: the app downloads LibreOffice only after the user agrees to it (policy 10.2.x), and local models are downloaded by the user.
6. Each release: a new submission with that release's URL.

Signing: policy 10.2.9 says every PE file "must" be signed, while the certification page calls it "highly recommended"; in 2.2.3, 433 of 584 PE files were unsigned. The choice is to try certification as the files are. If it is flagged, sign only the unsigned `.dll`, `.pyd` and `.exe` files in a batch signing hook; every signed file then changes on every release, so differential updates grow.

## Listing fixes

Text to paste, the same everywhere:

> **Short:** Local-first desktop app for research over your own documents, with local AI models.
>
> **Long:** SurfSense is a local-first desktop app for research over your own documents. It parses and embeds them on this computer, answers questions about them with citations, and runs its language, voice and image models locally. Free and open source (Apache-2.0), for Windows 10 and 11 (x64), macOS 13.3 or later (Apple Silicon) and Linux (x86_64; Ubuntu 22.04, Debian 12 or newer). Download: https://www.surfsense.com/downloads

| Site | Now | Fix |
|---|---|---|
| [AlternativeTo](https://alternativeto.net/software/surfsense/about/) | platforms Self-Hosted and Docker, website surfsense.net, the hosted product's description | Contribute → edit: platforms Windows, Mac and Linux (drop Self-Hosted and Docker), website https://www.surfsense.com, the long text |
| [OpenAlternative](https://openalternative.co/surfsense) | "Self-hostable NotebookLM alternative that lets teams…", Self-hosted: Yes | claim or ask for an edit: the long text, without "self-hostable" or "for teams" |
| [SourceForge mirror](https://sourceforge.net/projects/surfsense.mirror/) | offers `SurfSense-arm64.zip` to everyone | ask the mirror team to make the default download `SurfSense-Setup.exe` on Windows, `SurfSense-arm64.dmg` on macOS and `SurfSense.AppImage` on Linux |
| [Uptodown](https://uptodown.dev) | not listed | Developer Console → Add new app, once for Windows and once for Mac. It takes the file itself, not a link, so upload `SurfSense-Setup.exe` and `SurfSense-arm64.dmg`, and each new version under Files |
| [AppImage catalog](https://github.com/AppImage/appimage.github.io/blob/master/apps/SurfSense.md) | generated from 2.0.3, whose description has an unquoted colon, so appimage.github.io/SurfSense/ is a 404 | comment `/retest` on [#5102](https://github.com/AppImage/appimage.github.io/pull/5102); if a merged pull request does not re-run, open an issue asking for `apps/SurfSense.md` to be regenerated |
| [FileHorse](https://www.filehorse.com/contact/) | not listed | the contact form, below |
| [TechSpot](https://www.techspot.com/about/) | not listed | email the downloads editor, below |

For FileHorse and TechSpot, one message each:

> Hello, I maintain SurfSense, an open-source desktop app, and would like it listed.
> Name and version: SurfSense X.Y.Z. Website: https://www.surfsense.com. Download: https://www.surfsense.com/downloads. License: open source, Apache-2.0. Platforms: Windows 10 and 11 (x64), macOS 13.3 or later (Apple Silicon), Linux (x86_64).
> (the long text)
> Icon and screenshots are attached. I am the project's maintainer.
