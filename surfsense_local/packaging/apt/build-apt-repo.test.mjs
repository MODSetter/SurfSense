import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { gunzipSync } from "node:zlib"

const SCRIPT = fileURLToPath(new URL("./build-apt-repo.sh", import.meta.url))
const TOOLS = ["apt-ftparchive", "dpkg-deb", "gpg", "gpgv", "gzip"]

// The release job runs this on Ubuntu; elsewhere these tools are rarely all present.
const missing =
  process.platform !== "linux"
    ? "apt repositories are built on Linux"
    : spawnSync("bash", ["-c", `for t in ${TOOLS.join(" ")}; do command -v "$t" >/dev/null || exit 1; done`]).status !== 0
      ? `needs ${TOOLS.join(", ")}`
      : false

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex")

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options })
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed:\n${result.stderr}`)
  return result.stdout
}

/** A scratch folder removed after the test, along with any gpg-agent started in it. */
function scratch(t) {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-apt-"))
  t.after(() => {
    spawnSync("gpgconf", ["--kill", "gpg-agent"], { env: { ...process.env, GNUPGHOME: join(dir, "gnupg") } })
    rmSync(dir, { recursive: true, force: true })
  })
  return dir
}

/** An armored secret signing key, generated in its own keyring under `dir`. */
function signingKey(dir, passphrase) {
  const env = { ...process.env, GNUPGHOME: join(dir, "gnupg") }
  mkdirSync(env.GNUPGHOME, { mode: 0o700 })
  const unlock = ["--batch", "--pinentry-mode", "loopback", "--passphrase", passphrase]
  run("gpg", [...unlock, "--quick-gen-key", "SurfSense apt test <apt-test@example.invalid>", "ed25519", "sign", "never"], { env })
  return run("gpg", [...unlock, "--armor", "--export-secret-keys", "apt-test@example.invalid"], { env })
}

/** A minimal deb with the package name the install scripts ask apt for. */
function deb(dir) {
  const root = join(dir, "pkg")
  mkdirSync(join(root, "DEBIAN"), { recursive: true })
  mkdirSync(join(root, "opt", "SurfSense"), { recursive: true })
  writeFileSync(join(root, "opt", "SurfSense", "surfsense-local"), "#!/bin/sh\n", { mode: 0o755 })
  writeFileSync(
    join(root, "DEBIAN", "control"),
    [
      "Package: surfsense-local-electron",
      "Version: 2.3.0",
      "Architecture: amd64",
      "Maintainer: SurfSense <apt-test@example.invalid>",
      "Description: test package",
      "",
    ].join("\n")
  )
  const path = join(dir, "build-output.deb")
  run("dpkg-deb", ["--build", root, path])
  return path
}

/** `gpgv` with only the repository's own keyring, as apt checks it through `signed-by`. */
function verify(out, ...files) {
  return spawnSync("gpgv", ["--keyring", join(out, "surfsense-archive-keyring.gpg"), ...files], { encoding: "utf8" })
}

/** The text a clearsigned file signs: after its armor headers, before the signature, dash-escaping undone. */
function clearsignedText(file) {
  const body = file.split(/^-----BEGIN PGP SIGNED MESSAGE-----\n(?:.+\n)*\n/m)[1] ?? ""
  return body.split(/^-----BEGIN PGP SIGNATURE-----$/m)[0].replace(/^- /gm, "")
}

/** The `SHA256:` section of a Release file, as { name: { hash, size } }. */
function releaseSha256(release) {
  const section = release.split(/^SHA256:\n/m)[1]?.split(/^\S/m)[0] ?? ""
  return Object.fromEntries(
    section
      .split("\n")
      .filter(Boolean)
      .map((line) => line.trim().split(/\s+/))
      .map(([hash, size, name]) => [name, { hash, size: Number(size) }])
  )
}

test("builds a signed flat repository whose Packages entry is the exact deb given", { skip: missing }, (t) => {
  const dir = scratch(t)
  const debPath = deb(dir)
  const out = join(dir, "out")

  run("bash", [SCRIPT, debPath, out], { env: { ...process.env, APT_GPG_PRIVATE_KEY: signingKey(dir, "") } })

  assert.deepEqual(readdirSync(out).sort(), [
    "InRelease",
    "Packages",
    "Packages.gz",
    "Release",
    "Release.gpg",
    "surfsense-archive-keyring.gpg",
  ])
  const packages = readFileSync(join(out, "Packages"))
  const fields = packages.toString("utf8").split("\n")
  assert.ok(fields.includes("Package: surfsense-local-electron"))
  assert.ok(fields.includes("Filename: ./SurfSense.deb"), "apt resolves the deb next to Packages, at releases/latest/download/")
  assert.ok(fields.includes(`SHA256: ${sha256(readFileSync(debPath))}`))
  assert.deepEqual(gunzipSync(readFileSync(join(out, "Packages.gz"))), packages)

  const release = readFileSync(join(out, "Release"), "utf8")
  const gz = readFileSync(join(out, "Packages.gz"))
  assert.deepEqual(releaseSha256(release), {
    Packages: { hash: sha256(packages), size: packages.length },
    "Packages.gz": { hash: sha256(gz), size: gz.length },
  })

  const inRelease = verify(out, join(out, "InRelease"))
  assert.equal(inRelease.status, 0, inRelease.stderr)
  const signed = clearsignedText(readFileSync(join(out, "InRelease"), "utf8"))
  assert.equal(signed.trimEnd(), release.trimEnd(), "InRelease signs the same Release")
  const detached = verify(out, join(out, "Release.gpg"), join(out, "Release"))
  assert.equal(detached.status, 0, detached.stderr)

  // signed-by takes a binary keyring; an armored one fails every apt update.
  assert.ok(readFileSync(join(out, "surfsense-archive-keyring.gpg"))[0] & 0x80)
})

test("signs with a passphrase-protected key when APT_GPG_PASSPHRASE is given", { skip: missing }, (t) => {
  const dir = scratch(t)
  const out = join(dir, "out")
  const env = { ...process.env, APT_GPG_PRIVATE_KEY: signingKey(dir, "apt test passphrase"), APT_GPG_PASSPHRASE: "apt test passphrase" }

  run("bash", [SCRIPT, deb(dir), out], { env })

  const result = verify(out, join(out, "InRelease"))
  assert.equal(result.status, 0, result.stderr)
})

test("refuses to build an unsigned repository", { skip: missing }, (t) => {
  const dir = scratch(t)
  const env = { ...process.env }
  delete env.APT_GPG_PRIVATE_KEY

  const result = spawnSync("bash", [SCRIPT, deb(dir), join(dir, "out")], { encoding: "utf8", env })

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /APT_GPG_PRIVATE_KEY/)
  assert.throws(() => readdirSync(join(dir, "out")), { code: "ENOENT" })
})
