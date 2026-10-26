import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { publishedRelease } from "./release.mjs"
import { wingetManifests } from "./winget.mjs"

const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))
const BUILDER_YML = new URL("../../electron/electron-builder.yml", import.meta.url)
const release = publishedRelease(JSON.parse(readFileSync(FIXTURE, "utf8")), "2.3.0")
const manifests = wingetManifests(release)

const DIR = "manifests/s/SurfSense/SurfSense/2.3.0"
const installer = manifests[`${DIR}/SurfSense.SurfSense.installer.yaml`]
const locale = manifests[`${DIR}/SurfSense.SurfSense.locale.en-US.yaml`]
const version = manifests[`${DIR}/SurfSense.SurfSense.yaml`]

/** UUID v5, as electron-builder names its NSIS uninstall key after the appId. */
function uuidV5(name, namespace) {
  const bytes = createHash("sha1")
    .update(Buffer.concat([Buffer.from(namespace.replaceAll("-", ""), "hex"), Buffer.from(name)]))
    .digest()
    .subarray(0, 16)
  bytes[6] = (bytes[6] & 0x0f) | 0x50
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = bytes.toString("hex")
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-")
}

test("writes the three files winget-pkgs keeps per version, at its path", () => {
  assert.deepEqual(Object.keys(manifests).sort(), [
    `${DIR}/SurfSense.SurfSense.installer.yaml`,
    `${DIR}/SurfSense.SurfSense.locale.en-US.yaml`,
    `${DIR}/SurfSense.SurfSense.yaml`,
  ])
  for (const [file, type] of [
    [installer, "installer"],
    [locale, "defaultLocale"],
    [version, "version"],
  ]) {
    assert.match(file, /^PackageIdentifier: SurfSense\.SurfSense$/m)
    assert.match(file, /^PackageVersion: 2\.3\.0$/m)
    assert.match(file, new RegExp(`^ManifestType: ${type}\\nManifestVersion: 1\\.12\\.0\\n$`, "m"))
    assert.match(file, new RegExp(`^# yaml-language-server: \\$schema=https://aka\\.ms/winget-manifest\\.${type}\\.1\\.12\\.0\\.schema\\.json\\n\\n`))
  }
  assert.match(version, /^DefaultLocale: en-US$/m)
})

test("installs the per-user x64 NSIS build from this tag, checked by GitHub's digest", () => {
  assert.match(installer, /^InstallerType: nullsoft$/m)
  assert.match(installer, /^InstallerSwitches:\n  Upgrade: --updated$/m)
  assert.match(installer, /^UpgradeBehavior: install$/m)
  assert.match(installer, /^ReleaseDate: 2026-11-04$/m)
  assert.match(
    installer,
    new RegExp(
      "^Installers:\\n" +
        "- Architecture: x64\\n" +
        "  Scope: user\\n" +
        "  InstallerUrl: https://github\\.com/MODSetter/SurfSense/releases/download/v2\\.3\\.0/SurfSense-Setup\\.exe\\n" +
        `  InstallerSha256: ${"C".repeat(64)}\\n`,
      "m"
    )
  )
})

test("ProductCode is the uninstall key electron-builder derives from the appId", () => {
  const appId = readFileSync(BUILDER_YML, "utf8").match(/^appId: (.+)$/m)[1].trim()
  const key = uuidV5(appId, "50e065bc-3134-11e6-9bab-38c9862bdaf3")
  assert.match(installer, new RegExp(`^ProductCode: ${key}$`, "m"))
})

test("lets winget upgrade the app, since its own updater is off by default", () => {
  assert.doesNotMatch(installer, /RequireExplicitUpgrade/)
})

test("the default locale describes the app and links this tag's notes", () => {
  assert.match(locale, /^PackageLocale: en-US$/m)
  assert.match(locale, /^Publisher: SurfSense$/m)
  assert.match(locale, /^PackageName: SurfSense$/m)
  assert.match(locale, /^License: Apache-2\.0$/m)
  assert.match(locale, /^PackageUrl: https:\/\/www\.surfsense\.com$/m)
  assert.match(locale, /^ReleaseNotesUrl: https:\/\/github\.com\/MODSetter\/SurfSense\/releases\/tag\/v2\.3\.0$/m)
  assert.match(locale, /^ShortDescription: \S.+$/m)
  assert.match(locale, /^Moniker: surfsense$/m)
})

test("every value is a plain YAML scalar that needs no quoting", () => {
  for (const file of [installer, locale, version]) {
    for (const line of file.split("\n")) {
      if (line === "" || line.startsWith("#")) continue
      const value = line.match(/^ *(?:- )?[A-Za-z]+: (.*)$/)?.[1] ?? line.match(/^ *- (.*)$/)?.[1]
      if (value === undefined || value === "") continue
      assert.doesNotMatch(value, /: | #|^- |^[?:,[\]{}#&*!|>'"%@`]/, line)
    }
  }
})
