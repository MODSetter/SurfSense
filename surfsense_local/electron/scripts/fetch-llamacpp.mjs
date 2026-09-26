// Download and atomically stage the pinned llama.cpp build for this host.
//
// llama.cpp publishes about ten builds a day and has no stable channel, so the
// build number and its SHA-256 are both pinned here. The runtime this replaced
// verified no checksum at all; this does, because an unpinned generation runtime
// is the one dependency that can change under us between two identical builds.
//
// The GPU backend is Vulkan on every platform off Apple Silicon. It covers
// NVIDIA, AMD and Intel from one archive, its loader ships with Windows, and it
// is already what this app shipped: the previous runtime's CUDA runners were
// stripped at build time for exactly the same reason.
// Measured at b11050 on an RTX 3050, CUDA leads Vulkan 9.1% on prefill and 2.1%
// on decode, which is 0.66 s of an 11 s turn for 685 MB. See
// docs/proposals/cuda-backend.md.
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  lstatSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  renameSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { basename, dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

export const BUILD = "b11050"
const BASE = `https://github.com/ggml-org/llama.cpp/releases/download/${BUILD}`
const HERE = fileURLToPath(new URL(".", import.meta.url))
const OUT = join(HERE, "..", "llamacpp")

export const TARGETS = {
  "darwin-arm64": {
    asset: `llama-${BUILD}-bin-macos-arm64.tar.gz`,
    sha256: "e64c549a443d1353f440f436039d449a431fbcc1528b03838dda3d9a26530062", // pragma: allowlist secret
  },
  "win32-x64": {
    asset: `llama-${BUILD}-bin-win-vulkan-x64.zip`,
    sha256: "f1844840ad85b54405b6d5d0d9e8130a6d89c7094186b520fe4c1d9143290e7f", // pragma: allowlist secret
  },
  "linux-x64": {
    asset: `llama-${BUILD}-bin-ubuntu-vulkan-x64.tar.gz`,
    sha256: "eba230a6c76dee7422d1851651d7c4634fb6a39aed57e524a3612e9ed2bd1d89", // pragma: allowlist secret
  },
}

const key = `${process.platform}-${process.arch}`
const SERVER = process.platform === "win32" ? "llama-server.exe" : "llama-server"
const TAR =
  process.platform === "win32"
    ? join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe")
    : "tar"

const LIBRARY = /\.(dylib|so)(\.\d+)*$|\.dll$/i
// The archives carry 24 executables and we run one. Their per-tool support
// libraries go with them, which also shrinks the macOS notarization surface.
const OTHER_TOOL_LIBRARY = /^(lib)?llama-(?!server)[a-z0-9-]+-impl\./i

function isKept(name) {
  if (name === SERVER) return true
  if (OTHER_TOOL_LIBRARY.test(name)) return false
  return LIBRARY.test(name)
}

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

async function download(url, destination) {
  const response = await fetch(url, { redirect: "follow" })
  if (!response.ok) throw new Error(`download failed (${response.status}): ${url}`)
  writeFileSync(destination, Buffer.from(await response.arrayBuffer()))
}

/** Prove the pruned stage still runs, and that it can see its backends. */
function verifyStage(stage) {
  const output = execFileSync(join(stage, SERVER), ["--list-devices"], {
    cwd: stage,
    encoding: "utf8",
    timeout: 120_000,
    windowsHide: true,
  })
  if (!/Available devices|no devices found/i.test(output)) {
    throw new Error(`llama-server --list-devices said nothing useful: ${output}`)
  }
  return output
}

export function checkConfiguration() {
  for (const target of ["darwin-arm64", "win32-x64", "linux-x64"]) {
    const config = TARGETS[target]
    if (!config || !config.asset.includes(`-${BUILD}-`)) {
      throw new Error(`missing pinned ${BUILD} asset for ${target}`)
    }
    if (!/^[0-9a-f]{64}$/.test(config.sha256)) {
      throw new Error(`invalid SHA-256 for ${target}`)
    }
    if (target !== "darwin-arm64" && !config.asset.includes("vulkan")) {
      throw new Error(`${target} must ship the Vulkan build, got ${config.asset}`)
    }
  }
}

async function main() {
  checkConfiguration()
  if (process.argv.includes("--check")) {
    console.log(`llama.cpp ${BUILD} target matrix OK`)
    return
  }

  const target = TARGETS[key]
  if (!target) throw new Error(`no bundled llama.cpp for ${key}`)

  if (existsSync(join(OUT, SERVER))) {
    console.log(`llama.cpp ${BUILD} already staged in ${OUT}`)
    return
  }

  const work = mkdtempSync(join(tmpdir(), "surfsense-llamacpp-"))
  const unpacked = join(work, "unpacked")
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  try {
    mkdirSync(stage, { recursive: true })
    mkdirSync(unpacked, { recursive: true })

    const archive = join(work, target.asset)
    console.log(`downloading ${BASE}/${target.asset}`)
    await download(`${BASE}/${target.asset}`, archive)

    const actual = createHash("sha256").update(readFileSync(archive)).digest("hex")
    if (actual !== target.sha256) {
      throw new Error(
        `SHA-256 mismatch for ${target.asset}: expected ${target.sha256}, got ${actual}`,
      )
    }

    execFileSync(TAR, ["-xf", archive, "-C", unpacked], { stdio: "inherit" })
    const server = find(unpacked, (entry) => entry === SERVER)
    if (!server) throw new Error(`${target.asset} did not contain ${SERVER}`)

    // Windows archives are flat; macOS and Linux nest under one directory.
    const source = dirname(server)
    // macOS and Linux version their libraries through symlink chains
    // (libggml.dylib -> libggml.0.dylib -> libggml.0.24.0.dylib), and the
    // runtime loads by the name in the link. Copying only regular files leaves
    // llama-server unable to resolve its own @rpath entries, so recreate the
    // links rather than dereferencing them into duplicate copies.
    let kept = 0
    let bytes = 0
    for (const entry of readdirSync(source, { withFileTypes: true })) {
      if (!isKept(entry.name)) continue
      const from = join(source, entry.name)
      const to = join(stage, entry.name)
      if (entry.isSymbolicLink()) {
        symlinkSync(readlinkSync(from), to)
        kept += 1
        continue
      }
      if (!entry.isFile()) continue
      copyFileSync(from, to)
      if (process.platform !== "win32") chmodSync(to, 0o755)
      kept += 1
      bytes += lstatSync(from).size
    }

    const licence = find(unpacked, (entry) => entry.toUpperCase().startsWith("LICENSE"))
    if (licence) copyFileSync(licence, join(stage, "LICENSE"))

    verifyStage(stage)

    rmSync(backup, { recursive: true, force: true })
    if (existsSync(OUT)) renameSync(OUT, backup)
    try {
      renameSync(stage, OUT)
    } catch (error) {
      if (existsSync(backup)) renameSync(backup, OUT)
      throw error
    }
    rmSync(backup, { recursive: true, force: true })
    const mb = (bytes / 1024 / 1024).toFixed(1)
    console.log(`llama.cpp ${BUILD} staged in ${OUT}: ${kept} files, ${mb} MB (${basename(target.asset)})`)
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
