// Linux and macOS: compile sd-server from the pinned commit, because upstream's
// Linux archives need glibc 2.38 and its macOS one needs macOS 26.0.
//
// TODO: ask upstream (leejet/stable-diffusion.cpp) to publish a Linux archive
// built on Ubuntu 22.04 and a macOS one for 13.3, as llama.cpp does. Once a
// release does, download those as the Windows archive is and delete this.
import { execFileSync } from "node:child_process"
import { copyFileSync } from "node:fs"
import { availableParallelism } from "node:os"
import { join } from "node:path"

import { CMAKE, CXX_COMPILER, VULKAN_SDK, XCODE_TOOLS } from "../not-staged/tools.mjs"
import { COMMIT, SOURCE, SUBMODULES, TAG } from "./pins.mjs"
import { configureArgs } from "./recipe.mjs"

function output(cmd, args) {
  try {
    return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim()
  } catch {
    return null
  }
}

/** Everything this machine lacks to compile it, empty if nothing. */
export function missingToolchain() {
  const missing = []
  if (output("cmake", ["--version"]) == null) missing.push(CMAKE)
  if (process.platform === "darwin") {
    if (output("xcrun", ["--find", "clang"]) == null) missing.push(XCODE_TOOLS)
    return missing
  }
  if (output(process.env.CXX ?? "g++", ["--version"]) == null) missing.push(CXX_COMPILER)
  // ggml's Vulkan shaders are compiled at build time.
  if (output("glslc", ["--version"]) == null) missing.push(VULKAN_SDK)
  return missing
}

/** Build every target in `work`; returns the folder holding the server. */
export function compile(work) {
  const source = join(work, "source")
  const build = join(work, "build")
  const run = (cmd, args) => execFileSync(cmd, args, { stdio: "inherit" })

  run("git", ["-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1", "--branch", TAG, SOURCE, source])
  const head = output("git", ["-C", source, "rev-parse", "HEAD"])
  if (head !== COMMIT) throw new Error(`sd.cpp ${TAG} is ${head}, not the pinned ${COMMIT}`)
  run("git", ["-C", source, "submodule", "update", "--init", "--depth", "1", "--", ...SUBMODULES])

  const ninja = output("ninja", ["--version"]) != null
  run("cmake", ["-S", source, "-B", build, ...(ninja ? ["-G", "Ninja"] : []), ...configureArgs(process.platform)])
  // Every target, not just sd-server: ggml's backend modules are loaded at
  // start, so nothing links them and a server-only build leaves them out.
  run("cmake", ["--build", build, "--config", "Release", "--parallel", String(availableParallelism())])

  const binaries = join(build, "bin")
  // Beside the server, under the names upstream's archives give them.
  copyFileSync(join(source, "LICENSE"), join(binaries, "stable-diffusion.cpp.txt"))
  copyFileSync(join(source, "ggml", "LICENSE"), join(binaries, "ggml.txt"))
  return binaries
}
