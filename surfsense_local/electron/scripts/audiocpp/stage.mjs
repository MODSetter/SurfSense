// `pnpm build:audiocpp`: stage audio.cpp's server and eSpeak-ng into
// electron/audiocpp, swapped in whole once the server lists its devices.
// macOS downloads upstream's archive; Windows and Linux compile the pinned
// source. Without a toolchain the app runs without local audio, unless
// --strict, which release CI passes.
import { execFileSync } from "node:child_process"
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, renameSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { compile, missingToolchain } from "./compile.mjs"
import { stageEspeak } from "./espeak.mjs"
import { copyMsvcRuntime } from "./msvc.mjs"
import { TAG } from "./pins.mjs"
import { copyServerFiles, SERVER } from "./server-files.mjs"
import { unpackUpstream } from "./upstream-archive.mjs"

const OUT = fileURLToPath(new URL("../../audiocpp", import.meta.url))
const HOSTS = ["darwin-arm64", "linux-x64", "win32-x64"]

/** Prove the stage runs from its own directory and finds its CPU library. */
function verifyStage(stage) {
  const output = execFileSync(join(stage, SERVER), ["--list-devices"], {
    cwd: stage,
    encoding: "utf8",
    timeout: 120_000,
    windowsHide: true,
  })
  if (!/^available_devices=/m.test(output)) {
    throw new Error(`audiocpp_server --list-devices said nothing useful: ${output}`)
  }
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
    console.log(`audio.cpp ${TAG} already staged in ${OUT}`)
    return
  }

  const host = `${process.platform}-${process.arch}`
  const missing = !HOSTS.includes(host)
    ? `a supported host, not ${host}`
    : process.platform === "darwin"
      ? null
      : missingToolchain()
  if (missing) {
    if (strict) throw new Error(`staging audio.cpp needs ${missing}`)
    // Empty, so the packager still finds the folder; the sidecar never starts.
    mkdirSync(OUT, { recursive: true })
    console.warn(`audio.cpp not staged: it needs ${missing}. Local audio is unavailable.`)
    return
  }

  const work = mkdtempSync(join(tmpdir(), "surfsense-audiocpp-"))
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  try {
    mkdirSync(stage)
    if (process.platform !== "darwin") {
      console.log(`compiling audio.cpp ${TAG}; this runs once and takes a few minutes`)
    }
    const files = process.platform === "darwin" ? await unpackUpstream(work) : compile(work)
    copyServerFiles(files, stage)
    if (process.platform === "win32") copyMsvcRuntime(stage)
    await stageEspeak(work, stage)
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
    console.log(`audio.cpp ${TAG} staged in ${OUT}: ${megabytes(OUT)} MB`)
  } finally {
    rmSync(work, { recursive: true, force: true })
    rmSync(stage, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
