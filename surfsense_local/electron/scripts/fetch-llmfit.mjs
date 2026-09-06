// Download and atomically stage the pinned official llmfit binary for this host.
// SHA-256 values are from the matching .sha256 assets on the v1.1.11 release.
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { basename, join } from "node:path"
import { fileURLToPath } from "node:url"

export const VERSION = "1.1.11"
const TAG = `v${VERSION}`
const BASE = `https://github.com/AlexsJones/llmfit/releases/download/${TAG}`
const HERE = fileURLToPath(new URL(".", import.meta.url))
const OUT = join(HERE, "..", "llmfit")

export const TARGETS = {
  "linux-x64": {
    asset: `llmfit-${TAG}-x86_64-unknown-linux-musl.tar.gz`,
    sha256: "ec5e2ac6438ba7bc1d6452a581087f2a6533d504136c1f2a70500b0f558896c5",
  },
  "darwin-arm64": {
    asset: `llmfit-${TAG}-aarch64-apple-darwin.tar.gz`,
    sha256: "f42249d8af58067dd47ef25f997be24ed2a7c6659499bfd16e7c8c431c6e8baf",
  },
  "darwin-x64": {
    asset: `llmfit-${TAG}-x86_64-apple-darwin.tar.gz`,
    sha256: "9c9f56ccf64fee455c5a38b14aa3dd92d95755778e926f986de1c427b6ced136",
  },
  "win32-x64": {
    asset: `llmfit-${TAG}-x86_64-pc-windows-msvc.zip`,
    sha256: "3255ed3ab916a0d1034cf11288f53c2790be8c7194b3df7325d627614548a65a",
  },
}

const key = `${process.platform}-${process.arch}`
const binaryName = process.platform === "win32" ? "llmfit.exe" : "llmfit"

function find(root, predicate) {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name)
    if (entry.isDirectory()) {
      const nested = find(path, predicate)
      if (nested) return nested
    } else if (predicate(entry.name)) {
      return path
    }
  }
}

function verifyVersion(binary) {
  const output = execFileSync(binary, ["--version"], {
    encoding: "utf8",
    timeout: 10_000,
    windowsHide: true,
  }).trim()
  if (!new RegExp(`\\b${VERSION.replaceAll(".", "\\.")}\\b`).test(output)) {
    throw new Error(`expected llmfit ${VERSION}, got: ${output || "<empty>"}`)
  }
}

async function download(url, destination) {
  const response = await fetch(url, { redirect: "follow" })
  if (!response.ok) throw new Error(`download failed (${response.status}): ${url}`)
  writeFileSync(destination, Buffer.from(await response.arrayBuffer()))
}

async function copyReleaseDocument(unpacked, stage, name, required = false) {
  const archived = find(unpacked, (entry) => entry.toUpperCase() === name)
  if (archived) {
    copyFileSync(archived, join(stage, name))
    return
  }

  try {
    const response = await fetch(
      `https://raw.githubusercontent.com/AlexsJones/llmfit/${TAG}/${name}`,
    )
    if (response.ok) {
      writeFileSync(join(stage, name), Buffer.from(await response.arrayBuffer()))
    } else if (required) {
      throw new Error(`upstream ${name} unavailable (${response.status})`)
    }
  } catch (error) {
    if (required) throw error
  }
}

export function checkConfiguration() {
  const expected = ["linux-x64", "darwin-arm64", "darwin-x64", "win32-x64"]
  for (const target of expected) {
    const config = TARGETS[target]
    if (!config || !config.asset.startsWith(`llmfit-${TAG}-`)) {
      throw new Error(`missing official ${TAG} asset for ${target}`)
    }
    if (!/^[0-9a-f]{64}$/.test(config.sha256)) {
      throw new Error(`invalid SHA-256 for ${target}`)
    }
  }
}

async function main() {
  checkConfiguration()
  if (process.argv.includes("--check")) {
    console.log(`llmfit ${VERSION} target matrix OK`)
    return
  }

  const target = TARGETS[key]
  if (!target) throw new Error(`no bundled llmfit for ${key}`)
  const binaryOnly = process.argv.includes("--binary-only")

  const existing = join(OUT, binaryName)
  if (existsSync(existing)) {
    try {
      verifyVersion(existing)
      if (binaryOnly || existsSync(join(OUT, "LICENSE"))) {
        console.log(`llmfit ${VERSION} already staged in ${OUT}`)
        return
      }
    } catch (error) {
      console.warn(`replacing invalid llmfit stage: ${error.message}`)
    }
  }

  const work = mkdtempSync(join(tmpdir(), "surfsense-llmfit-"))
  const unpacked = join(work, "unpacked")
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  try {
    rmSync(stage, { recursive: true, force: true })
    mkdirSync(stage, { recursive: true })
    mkdirSync(unpacked, { recursive: true })

    const archive = join(work, target.asset)
    const url = `${BASE}/${target.asset}`
    console.log(`downloading ${url}`)
    await download(url, archive)

    const actual = createHash("sha256").update(readFileSync(archive)).digest("hex")
    if (actual !== target.sha256) {
      throw new Error(`SHA-256 mismatch for ${target.asset}: expected ${target.sha256}, got ${actual}`)
    }

    // bsdtar is available on all supported packaging runners and reads zip too.
    execFileSync("tar", ["-xf", archive, "-C", unpacked], { stdio: "inherit" })
    const extracted = find(unpacked, (entry) => entry === binaryName)
    if (!extracted) throw new Error(`${target.asset} did not contain ${binaryName}`)
    copyFileSync(extracted, join(stage, binaryName))
    if (process.platform !== "win32") chmodSync(join(stage, binaryName), 0o755)

    await copyReleaseDocument(unpacked, stage, "LICENSE", !binaryOnly)
    await copyReleaseDocument(unpacked, stage, "NOTICE")
    verifyVersion(join(stage, binaryName))

    rmSync(backup, { recursive: true, force: true })
    if (existsSync(OUT)) renameSync(OUT, backup)
    try {
      renameSync(stage, OUT)
    } catch (error) {
      if (existsSync(backup)) renameSync(backup, OUT)
      throw error
    }
    rmSync(backup, { recursive: true, force: true })
    console.log(`llmfit ${VERSION} staged in ${OUT} (${basename(target.asset)})`)
  } finally {
    rmSync(work, { recursive: true, force: true })
    rmSync(stage, { recursive: true, force: true })
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
