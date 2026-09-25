// `pnpm build:sdcpp`: stage stable-diffusion.cpp's sd-server into
// electron/sdcpp, swapped in whole once it starts from its own folder.
// Windows downloads upstream's archive; Linux and macOS compile the pinned
// source. Without a toolchain the app runs without local images, unless
// --strict, which release CI passes.
import { execFileSync } from "node:child_process"
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, renameSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { copyMsvcRuntime, visualStudio } from "../msvc-runtime.mjs"
import { compile, missingToolchain } from "./compile.mjs"
import { TAG } from "./pins.mjs"
import { copyServerFiles, SERVER } from "./server-files.mjs"
import { unpackWindowsArchive } from "./windows-archive.mjs"

const OUT = fileURLToPath(new URL("../../sdcpp", import.meta.url))
const HOSTS = ["darwin-arm64", "linux-x64", "win32-x64"]

/** Prove the server starts from its own directory and finds its libraries. */
function verifyStage(stage) {
  execFileSync(join(stage, SERVER), ["--help"], {
    cwd: stage,
    stdio: "ignore",
    timeout: 60_000,
    windowsHide: true,
  })
}

function megabytes(root) {
  let total = 0
  for (const entry of readdirSync(root, { withFileTypes: true, recursive: true })) {
    if (entry.isFile()) total += lstatSync(join(entry.parentPath, entry.name)).size
  }
  return (total / 1024 / 1024).toFixed(1)
}

async function main() {
  const strict = process.argv.includes("--strict")
  if (existsSync(join(OUT, SERVER))) {
    console.log(`sd-server ${TAG} already staged in ${OUT}`)
    return
  }

  const host = `${process.platform}-${process.arch}`
  const missing = !HOSTS.includes(host)
    ? `a supported host, not ${host}`
    : process.platform === "win32"
      ? visualStudio()
        ? null
        : "Visual Studio 2022 or newer with the C++ tools, for the runtime it ships"
      : missingToolchain()
  if (missing) {
    if (strict) throw new Error(`staging sd-server needs ${missing}`)
    // Empty, so the packager still finds the folder; the sidecar never starts.
    mkdirSync(OUT, { recursive: true })
    console.warn(`sd-server not staged: it needs ${missing}. Local images are unavailable.`)
    return
  }

  const work = mkdtempSync(join(tmpdir(), "surfsense-sdcpp-"))
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  try {
    mkdirSync(stage)
    if (process.platform !== "win32") {
      console.log(`compiling sd.cpp ${TAG}; this runs once and takes several minutes`)
    }
    const binaries = process.platform === "win32" ? await unpackWindowsArchive(work) : compile(work)
    copyServerFiles(binaries, stage)
    // Upstream's ggml is built with OpenMP on Windows.
    if (process.platform === "win32") copyMsvcRuntime(stage, { openmp: true })
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
    console.log(`sd-server ${TAG} staged in ${OUT}: ${megabytes(OUT)} MB`)
  } finally {
    rmSync(work, { recursive: true, force: true })
    rmSync(stage, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
