// SurfSense.SurfSense's manifests for microsoft/winget-pkgs. The first version goes
// in by hand; release-channels.yml's winget-releaser writes every later one.
import { DESCRIPTION, HOMEPAGE, LICENSE, NAME, PUBLISHER, REPO, SUMMARY } from "./listing.mjs"

const ID = "SurfSense.SurfSense"
// What winget-pkgs merges today (Obsidian, LM Studio and Notion all write 1.12.0).
const MANIFEST_VERSION = "1.12.0"
// electron-builder's NSIS uninstall key, the UUID v5 of the appId com.surfsense.app.
// winget matches the installed app by it, as it does Obsidian's and LM Studio's.
const PRODUCT_CODE = "9a7516bd-33e2-5724-857c-bd937d1ea1f8"
const TAGS = ["ai", "citations", "documents", "knowledge-base", "llm", "local-ai", "offline", "rag", "research"]

function manifest(type, version, body) {
  return [
    `# yaml-language-server: $schema=https://aka.ms/winget-manifest.${type}.${MANIFEST_VERSION}.schema.json`,
    "",
    `PackageIdentifier: ${ID}`,
    `PackageVersion: ${version}`,
    ...body,
    `ManifestType: ${type}`,
    `ManifestVersion: ${MANIFEST_VERSION}`,
    "",
  ].join("\n")
}

/**
 * The installer, defaultLocale and version manifests for `release`, at their
 * winget-pkgs paths. The installer is electron-builder's one-click per-user NSIS:
 * winget's nullsoft defaults pass /S, and `--updated` tells it an upgrade is running.
 * No RequireExplicitUpgrade, because the in-app updater is off by default.
 */
export function wingetManifests(release) {
  const { version } = release
  const setup = release.asset("SurfSense-Setup.exe")
  const dir = `manifests/s/SurfSense/SurfSense/${version}`

  const installer = manifest("installer", version, [
    "InstallerType: nullsoft",
    "InstallerSwitches:",
    "  Upgrade: --updated",
    "UpgradeBehavior: install",
    `ProductCode: ${PRODUCT_CODE}`,
    `ReleaseDate: ${release.date}`,
    "Installers:",
    "- Architecture: x64",
    "  Scope: user",
    `  InstallerUrl: ${setup.url}`,
    `  InstallerSha256: ${setup.sha256.toUpperCase()}`,
  ])
  const locale = manifest("defaultLocale", version, [
    "PackageLocale: en-US",
    `Publisher: ${PUBLISHER}`,
    `PublisherUrl: ${HOMEPAGE}`,
    `PublisherSupportUrl: https://github.com/${REPO}/issues`,
    `PrivacyUrl: ${HOMEPAGE}/privacy`,
    `Author: ${PUBLISHER}`,
    `PackageName: ${NAME}`,
    `PackageUrl: ${HOMEPAGE}`,
    `License: ${LICENSE}`,
    `LicenseUrl: https://github.com/${REPO}/blob/main/LICENSE`,
    `ShortDescription: ${SUMMARY}`,
    `Description: ${DESCRIPTION}`,
    "Moniker: surfsense",
    "Tags:",
    ...TAGS.map((tag) => `- ${tag}`),
    `ReleaseNotesUrl: ${release.notesUrl}`,
  ])
  const versionFile = manifest("version", version, ["DefaultLocale: en-US"])

  return {
    [`${dir}/${ID}.installer.yaml`]: installer,
    [`${dir}/${ID}.locale.en-US.yaml`]: locale,
    [`${dir}/${ID}.yaml`]: versionFile,
  }
}
