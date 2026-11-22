# Update handover tests (2.4.0)

By hand, before tagging 2.4.0, on real machines and VMs. 2.4.0 is the last Windows release the company certificate can sign, so a mistake in its update check can never be fixed for Windows users ([ADR 0091](../docs/adr/0091-an-update-key-vouches-for-every-update-from-2-4-0-on.md), [updates](../docs/architecture/updates.md#who-signed-an-update)).

Nothing here touches `MODSetter/SurfSense`. Never push a tag, a prerelease or a test release there: 2.0.1 to 2.2.3 read the newest entry of its releases feed. Every test uses an admin policy mirror, or a throwaway repository of your own.

The unit and integration tests run in CI on every push (`cd surfsense_local/electron && pnpm test`). They cover a signature that is valid, missing, made by another key, made for another file or tampered with; an installer whose sha512 differs; Windows refusing a signature; and electron-updater's own updater taking an installer signed by another publisher, Node's `node.exe`. What follows is what only real installs show.

## 0. Prepare

1. **The secret and the variable.** Set the repository secret `UPDATE_SIGNING_KEY` to the whole of `update-signing-primary.private.pem`, and the repository variable `UPDATE_HANDOVER_VERSION` to `2.4.0`.
2. **A 2.4.0 test build, signed as the release will be.** Push this branch, then:

   ```bash
   gh workflow run release-local.yml --repo MODSetter/SurfSense --ref <branch> -f version=2.4.0 -f publish=never -f sign_windows=true
   ```

   `publish=never` keeps everything on the run. `sign_windows` signs through Azure, as a tag does, and spends signatures from the account's quota. When it is green, download from the run:
   - `surfsense-local-<os>`: the installers;
   - `update-manifests-<os>`: electron-builder's `stable*.yml`;
   - `update-manifests`: the signed `release*.yml`.

   Check that the `Smoke the dmg (macOS)` step printed the designated requirement and `accepted source=Notarized Developer ID`, and that the Windows leg passed `Check app-update.yml names a publisher`.
3. **A next build from another signer**, numbered 2.4.1. Run the same workflow with `-f version=2.4.1` and without `sign_windows`. Its `update-manifests` job fails, because 2.4.0 is not published to freeze from; only the installers are needed.
4. **A mirror.** Make a throwaway public repository, say `<you>/surfsense-update-test`, with a release `feed` whose assets stand for the mirror's files. Its download base `https://github.com/<you>/surfsense-update-test/releases/download/feed/` is an `https` mirror with no server to run. On each test machine, write the policy file naming it:

   | OS | File |
   |---|---|
   | Windows | `%ProgramData%\SurfSense\policy.json` |
   | macOS | `/Library/Application Support/SurfSense/policy.json` |
   | Linux | `/etc/surfsense/policy.json` |

   ```json
   { "updateFeed": "https://github.com/<you>/surfsense-update-test/releases/download/feed/" }
   ```

   Settings › About then says the checks go to that host. Remove the file when the tests are done.
5. **Signing a test manifest** with the primary key, on your own machine. Write the manifest for the file it names, then sign it under the name it will have. The script refuses a key the app does not trust.

   ```bash
   cd surfsense_local/electron
   node -e "const f=require('fs').readFileSync(process.argv[1]);console.log(require('crypto').createHash('sha512').update(f).digest('base64'), f.length)" <installer>
   UPDATE_SIGNING_KEY="$(cat ~/.surfsense-keys/update-signing-primary.private.pem)" \
     node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/update-signing/sign-manifest.mjs <unsigned.yml> <out>/release.yml
   ```

   A test manifest names a test version and a test build. Delete signed test manifests when the tests are done, and keep them out of any public place.

## 1. 2.3.1 updates to the 2.4.0 test build, through the mirror

On Windows, macOS and Linux (the AppImage, and the deb if you can), each with 2.3.1 installed and some sources and a saved API key.

1. Put on the mirror release: the 2.4.0 test build's installer for that platform (`SurfSense-Setup.exe` with its `.blockmap`; `SurfSense-arm64.zip` and `SurfSense-arm64.dmg` with their blockmaps; `SurfSense.AppImage`, `SurfSense.deb`), and its `stable.yml`, `stable-mac.yml` and `stable-linux.yml` from `update-manifests-<os>`.
2. In 2.3.1, Settings › About › Check now. Expect "Downloading", then "Restart to update"; restart.
3. Expect About to show 2.4.0, and sources, chats and the saved API key to work.
   - On Windows, the session log's `updater` lines show the signature check passing for `CN=SurfSense`.
   - On a Mac whose 2.3.0 or earlier crashes on the 1.3 GB zip, test from 2.3.1, the first version that installs it.
4. Repeat step 2 with `stable.yml` and `stable-mac.yml` replaced by the frozen form a later release will carry: `tag: v2.4.0` prepended to 2.4.0's own. 2.3.1 must take it just the same.

## 2. The 2.4.0 test build refuses what SurfSense did not sign

On the 2.4.0 test build from test 1, with the mirror still set:

1. Put `release.yml`, `release-mac.yml` and `release-linux.yml` from the `update-manifests` artifact on the mirror. Check now says SurfSense is up to date, since they name 2.4.0.
2. Replace the file for this platform with electron-builder's unsigned `stable*.yml`, renamed to `release*.yml`. Check now must fail with "Could not check for updates: the update mirror github.com could not be used (release.yml carries no SurfSense signature)", and nothing downloads.
3. Replace it with a signed manifest with one character changed, then with `release-mac.yml` renamed to `release.yml`. Both must fail with "(the signature on release.yml does not match)".

## 3. The 2.4.0 test build takes a build from another signer

**Windows**, on a VM with the 2.4.0 test build installed:

1. Make a test code-signing certificate, trust it on this VM only, and sign the 2.4.1 installer with it:

   ```powershell
   $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Update Handover Test" -CertStoreLocation Cert:\CurrentUser\My
   $file = "$env:TEMP\handover-test.cer"
   Export-Certificate -Cert $cert -FilePath $file
   Import-Certificate -FilePath $file -CertStoreLocation Cert:\LocalMachine\Root
   Import-Certificate -FilePath $file -CertStoreLocation Cert:\LocalMachine\TrustedPublisher
   Set-AuthenticodeSignature -FilePath .\SurfSense-Setup.exe -Certificate $cert -HashAlgorithm SHA256
   (Get-AuthenticodeSignature .\SurfSense-Setup.exe).Status
   ```

   The last line must say `Valid`.
2. Write `release.yml` for version 2.4.1 naming the re-signed `SurfSense-Setup.exe` (step 0.5), sign it, and put both on the mirror. Leave the 2.4.1 blockmap off, because re-signing changed the installer.
3. Check now in 2.4.0 must download, pass the check and restart into 2.4.1. The session log names `CN=Update Handover Test`.
4. On a second VM, or after removing the certificate from `LocalMachine\Root`, the same update must fail with "Windows does not trust its signature".
5. Remove the test certificate from both stores, and delete it from `CurrentUser\My`, when done.

**macOS**: Squirrel.Mac checks the new bundle against the running app's designated requirement. Check that requirement against apps from other teams:

```bash
codesign -d -r- /Applications/SurfSense.app
REQ="=$(sed -n 's/^designated => //p' surfsense_local/electron/build/designated-requirement.txt)"
codesign --verify --deep --strict -R="$REQ" "/Applications/<an app from another Developer ID team>.app" && echo accepted
codesign --verify --deep --strict -R="$REQ" "/System/Applications/Calculator.app" || echo refused
spctl -a -vv /Applications/SurfSense.app
```

- The first command prints the requirement, with no `identifier` and no `subject.OU`.
- Any third-party Developer ID app is accepted, Google Chrome or Visual Studio Code for example.
- An Apple-signed system app is refused, because it carries no Developer ID leaf.
- `spctl` says `accepted` and `source=Notarized Developer ID`.

A real update from another team waits for the maintainer's own Apple team.

**Linux** has no signer to change. A 2.4.1 AppImage through a signed `release-linux.yml` on the mirror must install, and an unsigned one must be refused, as in test 2.

## 4. 2.2.3 and 2.0.0 reach 2.4.0 through a frozen stable.yml

On a Windows VM, since these use electron-updater's GitHubProvider with the owner and repository from `resources\app-update.yml`.

1. In the throwaway repository, create two releases:
   - `v2.4.0`, holding the 2.4.0 test build's `SurfSense-Setup.exe`, its blockmap and its `stable.yml`;
   - then `v2.4.1`, holding only `stable.yml` frozen: `tag: v2.4.0` followed by 2.4.0's own `stable.yml`.

   `v2.4.1` must be both the newest entry and Latest.
2. Install 2.2.3. In its install folder, edit `resources\app-update.yml` so `owner` and `repo` name the throwaway repository. Leave `publisherName` as it is.
3. Check for updates (2.2.3 checks at launch once allowed). Expect it to download from the `v2.4.0` release, not `v2.4.1`, and to install 2.4.0. 2.2.3 reads the newest feed entry, `v2.4.1`, so this proves the tag line works.
4. Repeat with 2.0.0, which reads Latest instead.
5. Delete the throwaway repository's releases when done.

## 5. secret.bin survives a refused keychain prompt (macOS)

On the 2.4.0 test build with a saved API key:

1. In Keychain Access, open "SurfSense Safe Storage", Access Control, select "Confirm before allowing access" and remove SurfSense from the list.
2. Quit and relaunch SurfSense, and click **Deny** at the prompt. The app must still start. `~/.surfsense/electron/secret.bin.unreadable` exists, and the saved API key reads as unreadable rather than gone.
3. Relaunch and click **Always Allow**. The API key works again, and `secret.bin.unreadable` is gone.

## 6. Offline from SurfSense's servers

With every `*.surfsense.com` host pointed at `0.0.0.0` in the hosts file and no policy file, Check now on the 2.4.0 test build still reaches GitHub. Settings › About and the update prompt name only `github.com`.

## Record

| Test | Windows | macOS | Linux |
|---|---|---|---|
| 1. 2.3.1 to 2.4.0 | | | |
| 1.4 frozen stable file | | | |
| 2. unsigned and tampered refused | | | |
| 3. another signer | | requirement only | |
| 4. 2.2.3 and 2.0.0 | | n/a | n/a |
| 5. secret.bin | n/a | | n/a |
| 6. offline | | | |
