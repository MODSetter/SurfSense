// `pnpm build:audiocpp`: stage audio.cpp's server and eSpeak-ng into
// electron/audiocpp, swapped in whole once the server lists its devices and
// has a loader for every curated family.
// macOS downloads upstream's archive; Windows and Linux compile the pinned
// source. Without a toolchain the app runs without local audio, unless
// --strict, which release CI and `pnpm dist` pass.
import { execFileSync } from "node:child_process"
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, renameSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { verifyBuiltFamilies } from "./built-families.mjs"
import { compile, missingToolchain } from "./compile.mjs"
import { stageEspeak, trimStagedEspeak } from "./espeak/stage.mjs"
import { copyMsvcRuntime } from "../msvc-runtime.mjs"
import { NotStaged, notStaged } from "../not-staged/message.mjs"
import { packageManager } from "../not-staged/package-manager.mjs"
import { renameWhenUnlocked } from "../windows-locks/rename-when-unlocked.mjs"
import { TAG } from "./pins.mjs"
import { copyServerFiles, SERVER } from "./server-files.mjs"
import { stagedServer } from "./staged-server.mjs"
import { unpackUpstream } from "./upstream-archive.mjs"

function option(name) {
  const at = process.argv.indexOf(`--${name}`)
  return at === -1 ? undefined : process.argv[at + 1]
}

// Without --out, the desktop's folder. Linux builds only for the CPU, so the
// Docker image stages this same build (docs/proposals/docker/gpu.md).
const OUT = option("out") ?? fileURLToPath(new URL("../../electron/audiocpp", import.meta.url))
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

/** Whether `folder` can be swapped out now; on Windows a running server holds it. */
function canMove(folder, aside) {
  try {
    renameSync(folder, aside)
  } catch (error) {
    if (["EBUSY", "EPERM", "EACCES"].includes(error.code)) return false
    throw error
  }
  renameSync(aside, folder)
  return true
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
  const staged = await stagedServer(OUT)
  if (staged.state === "current") {
    // A stage from before the trimming would ship every eSpeak dictionary.
    const removed = trimStagedEspeak(OUT)
    if (removed.length) console.log(`removed ${removed.length} eSpeak dictionaries no voice can reach from ${OUT}`)
    console.log(`audio.cpp ${TAG} already staged in ${OUT}`)
    return
  }
  // Without --strict a stale server is kept whenever staging again cannot finish:
  // it still serves every family it has, and pnpm dev goes on.
  const keep = (why) => {
    const message = `${why}\n\nThe audio.cpp in ${OUT} stays, though it ${staged.reason}.`
    if (strict) throw new NotStaged(message)
    console.warn(message)
  }

  const host = `${process.platform}-${process.arch}`
  const reason = !HOSTS.includes(host)
    ? `audio.cpp is not staged: it has no build for ${host}.`
    : process.platform === "darwin"
      ? null
      : notStaged(
          "audio.cpp",
          `on ${process.platform === "win32" ? "Windows" : "Linux"} it is compiled from source`,
          missingToolchain(),
          packageManager()
        )
  if (reason) {
    if (staged.state === "stale") return keep(reason)
    if (strict) throw new NotStaged(reason)
    // Empty, so the packager still finds the folder; the sidecar never starts.
    mkdirSync(OUT, { recursive: true })
    console.warn(`${reason}\n\nThe app runs without local audio.`)
    return
  }

  if (staged.state === "stale") console.log(`audio.cpp in ${OUT} ${staged.reason}; staging it again`)

  const started = Date.now()
  const work = mkdtempSync(join(tmpdir(), "surfsense-audiocpp-"))
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  // Found out before a few minutes of compiling, not after.
  if (staged.state === "stale" && !canMove(OUT, backup)) {
    rmSync(work, { recursive: true, force: true })
    return keep(`${OUT} is in use; quit SurfSense and run this again.`)
  }
  try {
    mkdirSync(stage, { recursive: true })
    if (process.platform !== "darwin") {
      console.log(`compiling audio.cpp ${TAG}; this runs once and takes a few minutes`)
    }
    const files = process.platform === "darwin" ? await unpackUpstream(work) : compile(work)
    copyServerFiles(files, stage)
    if (process.platform === "win32") copyMsvcRuntime(stage)
    await stageEspeak(work, stage)
    verifyStage(stage)
    await verifyBuiltFamilies(stage)

    rmSync(backup, { recursive: true, force: true })
    if (existsSync(OUT)) renameSync(OUT, backup)
    try {
      await renameWhenUnlocked(stage, OUT)
    } catch (error) {
      if (existsSync(backup)) renameSync(backup, OUT)
      throw error
    }
    rmSync(backup, { recursive: true, force: true })
    const minutes = ((Date.now() - started) / 60_000).toFixed(1)
    console.log(`audio.cpp ${TAG} staged in ${OUT}: ${megabytes(OUT)} MB, in ${minutes} min`)
  } catch (error) {
    if (staged.state !== "stale") throw error
    keep(`audio.cpp could not be staged again: ${error instanceof Error ? error.message : error}`)
  } finally {
    rmSync(work, { recursive: true, force: true })
    rmSync(stage, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error instanceof NotStaged ? error.message : error)
  process.exitCode = 1
})
