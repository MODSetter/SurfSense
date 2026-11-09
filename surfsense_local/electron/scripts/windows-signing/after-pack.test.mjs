import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { createRequire } from "node:module"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import afterPack from "./after-pack.mjs"
import { azureSigningScript, catalogLines } from "./azure-sign.mjs"
import { signatureStatuses } from "./signature-status.mjs"

const ELECTRON = fileURLToPath(new URL("../..", import.meta.url))
const PE = Buffer.from("MZ\x90\x00", "latin1")
const AZURE = {
  publisherName: "SurfSense Inc.",
  endpoint: "https://eus.codesigning.azure.net/",
  codeSigningAccountName: "SurfSense",
  certificateProfileName: "surfsense-prod",
}

/** A packed Windows app as electron-builder hands it to afterPack: release/win-unpacked. */
function packed(t, files) {
  const outDir = mkdtempSync(join(tmpdir(), "surfsense-after-pack-"))
  t.after(() => rmSync(outDir, { recursive: true, force: true }))
  const appOutDir = join(outDir, "win-unpacked")
  for (const [path, bytes] of Object.entries(files)) {
    mkdirSync(dirname(join(appOutDir, path)), { recursive: true })
    writeFileSync(join(appOutDir, path), bytes)
  }
  const context = (azureSignOptions, electronPlatformName = "win32") => ({
    outDir,
    appOutDir,
    electronPlatformName,
    packager: { platformSpecificBuildOptions: { azureSignOptions } },
  })
  return { appOutDir, context }
}

/** Signatures as Windows would report them, and a signer that makes them valid. */
function fakeSigning(signedAlready, { signs = true } = {}) {
  const valid = new Set(signedAlready)
  const calls = []
  return {
    calls,
    statusesOf: (files) => files.map((file) => (valid.has(file) ? "Valid" : "NotSigned")),
    sign: (files, azure, besideDir) => {
      calls.push({ files, azure, besideDir })
      if (signs) for (const file of files) valid.add(file)
    },
  }
}

const APP = {
  "SurfSense.exe": PE,
  "ffmpeg.dll": PE,
  "resources/backend/surfsense-backend.exe": PE,
  "resources/backend/_internal/python312.dll": PE,
  "resources/backend/_internal/chonkie_core/_chunk.cp312-win_amd64.pyd": PE,
  "resources/app.asar.unpacked/addon.NODE": PE,
  "resources/backend/_internal/README.txt": "not code",
  "resources/models/labels.dll": "a data file named like a library",
}

test("signs every native library without a valid signature, in one call", async (t) => {
  const { appOutDir, context } = packed(t, APP)
  const vendorSigned = join(appOutDir, "resources/backend/_internal/python312.dll")
  const signing = fakeSigning([vendorSigned])

  await afterPack(context(AZURE), signing)

  assert.equal(signing.calls.length, 1)
  assert.deepEqual(
    signing.calls[0].files,
    [
      "ffmpeg.dll",
      "resources/app.asar.unpacked/addon.NODE",
      "resources/backend/_internal/chonkie_core/_chunk.cp312-win_amd64.pyd",
    ]
      .map((path) => join(appOutDir, path))
      .sort()
  )
  assert.equal(signing.calls[0].azure, AZURE)
  assert.equal(signing.calls[0].besideDir, dirname(appOutDir))
})

test("a library still unsigned after signing stops the build, named", async (t) => {
  const { appOutDir, context } = packed(t, APP)
  const signing = fakeSigning([], { signs: false })

  await assert.rejects(afterPack(context(AZURE), signing), (error) =>
    error.message.includes(join(appOutDir, "resources/backend/_internal/chonkie_core/_chunk.cp312-win_amd64.pyd"))
  )
})

test("nothing is signed when every library already carries a signature", async (t) => {
  const { appOutDir, context } = packed(t, { "ffmpeg.dll": PE })
  const signing = fakeSigning([join(appOutDir, "ffmpeg.dll")])

  await afterPack(context(AZURE), signing)

  assert.equal(signing.calls.length, 0)
})

test("a dry run's build, with no Azure account, signs nothing", async (t) => {
  const { context } = packed(t, APP)
  const signing = fakeSigning([])

  await afterPack(context(undefined), signing)

  assert.equal(signing.calls.length, 0)
})

test("macOS and Linux builds are left to their own signing", async (t) => {
  const { context } = packed(t, APP)
  const signing = fakeSigning([])

  await afterPack(context(AZURE, "darwin"), signing)
  await afterPack(context(AZURE, "linux"), signing)

  assert.equal(signing.calls.length, 0)
})

test("the catalog lists each file relative to its own folder, where the module resolves it", () => {
  const release = join(tmpdir(), "release")
  const files = [join(release, "win-unpacked", "ffmpeg.dll"), join(release, "win-unpacked", "resources", "a.pyd")]

  assert.equal(catalogLines(release, files), [join("win-unpacked", "ffmpeg.dll"), join("win-unpacked", "resources", "a.pyd")].join("\n"))
  assert.throws(() => catalogLines(join(release, "win-unpacked", "resources"), files), /outside/)
})

test("Azure signs with the account and digests electron-builder signs the .exe files with", () => {
  const script = azureSigningScript("C:\\release\\to-sign.txt", { ...AZURE, codeSigningAccountName: "Surf'Sense" })

  assert.match(script, /Invoke-TrustedSigning /)
  assert.match(script, / -FilesCatalog 'C:\\release\\to-sign\.txt'/)
  assert.match(script, / -Endpoint 'https:\/\/eus\.codesigning\.azure\.net\/'/)
  assert.match(script, / -CodeSigningAccountName 'Surf''Sense'/)
  assert.match(script, / -CertificateProfileName 'surfsense-prod'/)
  assert.match(script, / -TimestampRfc3161 'http:\/\/timestamp\.acs\.microsoft\.com'/)
  assert.match(script, / -TimestampDigest 'SHA256'/)
  assert.match(script, / -FileDigest 'SHA256'/)
  assert.doesNotMatch(script, /publisherName|PublisherName/)
})

test("signatures are read from Windows itself", { skip: process.platform !== "win32" }, (t) => {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-signatures-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const unsigned = join(dir, "unsigned.dll")
  writeFileSync(unsigned, PE)

  // Node's own executable is signed by the OpenJS Foundation.
  assert.deepEqual(signatureStatuses([process.execPath, unsigned]).map((status) => status === "Valid"), [true, false])
  assert.deepEqual(signatureStatuses([]), [])
})

test("electron-builder.yml runs it after packing, and electron-builder loads it as the hook", async () => {
  const yml = readFileSync(join(ELECTRON, "electron-builder.yml"), "utf8")
  const hook = yml.match(/^afterPack:[ \t]*(\S+)/m)?.[1] ?? null
  assert.equal(hook, "./scripts/windows-signing/after-pack.mjs")
  const builder = createRequire(createRequire(join(ELECTRON, "package.json")).resolve("electron-builder"))
  const { resolveFunction } = builder("app-builder-lib/out/util/resolve")
  assert.equal(await resolveFunction("module", join(ELECTRON, hook), "afterPack", ELECTRON), afterPack)
})
