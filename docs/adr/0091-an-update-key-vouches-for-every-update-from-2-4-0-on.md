# ADR 0091: From 2.4.0 on, SurfSense's own update key vouches for an update, not a certificate's name

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** in part, [ADR 0070](0070-opt-in-id-less-update-checks-and-usage-statistics.md): the manifest request to `updates.surfsense.com` with GitHub behind it, from 2.4.0 on; amends [ADR 0020](0020-two-update-channels.md) and [ADR 0018](0018-keychain-envelope-encryption.md)
- **Source:** maintainer decision, 21 Nov 2026, in the free-transition plan kept outside the repository (no permalink)

## Context

SurfSense Inc. closes on 27 Nov 2026, and the app goes on free as the maintainer's own project. The company's signing identities end with it. The Azure account that holds Windows' Artifact Signing (publisher "SurfSense") closes right after the last company release, and the company's Apple team signs only until its membership lapses. The maintainer's own certificates come later, under names no build can know today.

Every installed app checks who signed an update, and an installed app cannot be changed:

- On Windows, every 2.x compares the installer's Authenticode signer with `publisherName: [SurfSense]` in its `app-update.yml`, exactly.
- On macOS, Squirrel.Mac holds an update to the running app's designated requirement, which names the company's Team ID. It checks once in SQRLUpdater and again in ShipIt.

A build signed by anyone else fails on every installed copy, so one last company-signed release has to sit between the two eras, and it has to accept builds from signers it cannot name.

## Decision

- **2.4.0 is the handover release:** the last build signed with the company certificates, and the one every older app updates to. The repository variable `UPDATE_HANDOVER_VERSION` names it, so the release workflow's path for a version is explicit.
- **Two Ed25519 key pairs vouch for every update from 2.4.0 on.** The maintainer holds both private halves. The primary signs in CI, as the secret `UPDATE_SIGNING_KEY`. The backup stays offline and never enters CI. Both public keys are compiled into the app ([`update-feed/update-keys.ts`](../../surfsense_local/electron/src/main/update-feed/update-keys.ts)), never read from configuration, environment or disk.
- **Each release carries signed manifests:** `release.yml`, `release-mac.yml` and `release-linux.yml`, electron-builder's names for a `release` channel. The first line of each is `surfsenseSignature: <base64>`. It holds an Ed25519 signature over `surfsense-update-manifest/1\n`, then the file's own name and `\n`, then the rest of the file byte for byte ([`manifest-signature.ts`](../../surfsense_local/electron/src/main/update-feed/manifest-signature.ts)). Binding the name means a signature made for one platform's file, or for anything else, never passes.
- **The app reads them straight from GitHub's `releases/latest/download/`**, or from an admin policy's mirror that copies them verbatim.
  - A manifest that neither compiled key verifies is refused, with the reason, and nothing else is asked: there is no other source, signed or not.
  - Installers come from the release the manifest's version names, or from the mirror. electron-updater checks each download's sha512 against the signed manifest, so the key vouches for the installer too.
- **Each platform's own check stays, relaxed to "validly signed, by anyone the OS trusts":**
  - **Windows:** `verifyUpdateCodeSignature` accepts any installer whose Authenticode status is Valid ([`installer-signature/`](../../surfsense_local/electron/src/main/installer-signature/)). NsisUpdater calls it only while `app-update.yml` names a publisher. So `publish.publisherName` in `electron-builder.yml` writes `SurfSense` whatever signs the build, and CI fails a build whose file names none.
  - **macOS:** every file signs with the designated requirement `anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] and certificate leaf[field.1.2.840.113635.100.6.1.13]`. That is a Developer ID signature from any team. It names no identifier, because electron-builder stamps the requirement on every nested helper and framework too.
  - **Linux** checks no signature, as before, and now has the manifest's.
- **Older apps reach 2.4.0 through frozen files.** Every release after 2.4.0 builds on the `release` channel and carries `stable.yml` and `stable-mac.yml` as 2.4.0's own, with `tag: v2.4.0` prepended.
  - 2.0.0 to 2.2.3 resolve files from that tag, and 2.2.4 to 2.3.1 from the version, so both download 2.4.0's company-signed files.
  - `stable-linux.yml` is the release's own, since old Linux apps check no signature.
  - The legacy bridge's `latest*.yml` stay.
- **A release with no signed Windows build** (`WINDOWS_SIGNING=off`) carries Latest's `release.yml` forward. Windows apps then stay on the last signed build instead of downloading one they would refuse.
- **A `secret.bin` the keychain refuses is set aside, never overwritten,** and tried again at each launch. A keychain prompt from a future Apple team, denied once, then does not orphan saved API keys ([ADR 0018](0018-keychain-envelope-encryption.md)).
- **A gate runs before the undraft** (`update-gate` in `release-local.yml`). The nine manifests must be there, and `release*.yml` must verify against the compiled keys. The frozen files must name 2.4.0, and 2.4.0's installers must still hash to what those files say. The build legs have already checked that `app-update.yml` names a publisher, and that the Mac app carries this requirement, passes Gatekeeper and is stapled.

## Consequences

- A certificate from any CA, in any name, ships updates to 2.4.0 and later with no second handover, while a compiled key signs the manifest.
- Losing both private keys strands 2.4.0 and later: their users reinstall by hand.
- A stolen primary key ships nothing on its own: the thief would also need the maintainer's GitHub account and a code-signing certificate. The backup then signs, and the next release stops trusting the primary.
- Neither platform pins a publisher any more. Shipping a build takes the update key and the release, not a certificate in SurfSense's name.
  - On macOS, the team-less requirement also governs keychain items and microphone grants made under it: any Developer ID app that calls itself `com.surfsense.app` would satisfy them.
  - A later release signed by the maintainer's own Apple team can name that team in its requirement. 2.4.0 still accepts that build.
- Update checks from 2.4.0 on no longer pass `updates.surfsense.com`, so only GitHub's download counts of `release*.yml` count them. The route stays for 2.2.4 to 2.3.1, which ask GitHub when it fails.
- 2.4.0's release is fixed forever: its assets are what the frozen files pin. It is never deleted, edited or re-uploaded.
- No bare tag or prerelease is pushed to `MODSetter/SurfSense` after the last release, because 2.0.1 to 2.2.3 read the newest entry of the releases feed. Tests use a throwaway repository or an admin mirror.
- Every release carries nine manifests: `stable*`, `release*` and `latest*`. Admin mirrors copy `release*.yml` verbatim.
- The first build from a new Apple team asks once for keychain access and again for the microphone; its release notes say to choose Always Allow.

## Where the code stands

- No signed build has run it yet. Still to check on real builds, by the manual list in [`UPDATE-HANDOVER-TESTS.md`](../../surfsense_local/UPDATE-HANDOVER-TESTS.md):
  - notarization and Gatekeeper with this requirement;
  - Squirrel.Mac installing a build from another team;
  - NsisUpdater installing a real installer from another publisher (tests cover it with Node's own signed `node.exe`).
- `install.ps1` still pins `CN=SurfSense`, and the afterPack native-library signing works only with Azure. The first release signed under another name has to change both.
- A release with no Windows build leaves the website's Windows link and `install.ps1` pointing at a Latest release with no Windows installer.
