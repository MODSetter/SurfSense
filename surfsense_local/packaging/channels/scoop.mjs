// bucket/surfsense.json for ScoopInstaller/Extras. After the first one, Excavator
// bumps it from checkver and autoupdate on its own.
import { HOMEPAGE, LICENSE, REPO, SUMMARY } from "./listing.mjs"

const INSTALLER = "SurfSense-Setup.exe"

/**
 * The manifest for `release`. It unpacks the NSIS installer as Extras' Electron apps
 * do (`#/dl.7z`, then `$PLUGINSDIR\app-64.7z`), and leaves Scoop in charge of updates:
 * the app reads resources\install-channel and stops updating itself, and with
 * app-update.yml gone electron-updater has no feed either. With no autoupdate hash,
 * Scoop reads the asset's GitHub digest instead of downloading the installer.
 */
export function scoopManifest(release) {
  const setup = release.asset(INSTALLER)
  const manifest = {
    version: release.version,
    description: `${SUMMARY}.`,
    homepage: HOMEPAGE,
    license: LICENSE,
    architecture: {
      "64bit": {
        url: `${setup.url}#/dl.7z`,
        hash: setup.sha256,
        pre_install: 'Expand-7zipArchive "$dir\\`$PLUGINSDIR\\app-64.7z" "$dir"',
      },
    },
    post_install: [
      'Remove-Item "$dir\\`$*", "$dir\\Uninstall*.exe", "$dir\\resources\\app-update.yml" -Recurse -Force',
      "# Scoop updates this install: the app reads the marker and leaves updating to it.",
      "Set-Content -Path \"$dir\\resources\\install-channel\" -Value 'scoop' -Encoding Ascii -NoNewline",
    ],
    shortcuts: [["SurfSense.exe", "SurfSense"]],
    checkver: { github: `https://github.com/${REPO}` },
    autoupdate: {
      architecture: {
        "64bit": { url: `https://github.com/${REPO}/releases/download/v$version/${INSTALLER}#/dl.7z` },
      },
    },
  }
  return { "surfsense.json": `${JSON.stringify(manifest, null, 4)}\n` }
}
