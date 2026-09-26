// Windows and Linux: compile audio.cpp's server from the pinned commit, because
// upstream's Linux archives need glibc 2.38 and its Windows one compiles
// AVX-512 into the executable.
//
// TODO: ask upstream (0xShug0/audio.cpp) to publish Linux archives built on
// Ubuntu 22.04 and Windows ones with per-CPU ggml libraries, as llama.cpp does.
// Once a release does, download those as fetch-llamacpp.mjs does and delete this.
import { execFileSync } from "node:child_process"
import { availableParallelism } from "node:os"
import { join } from "node:path"

import { visualStudio } from "../msvc-runtime.mjs"
import { CMAKE, GCC_13, VISUAL_STUDIO } from "../not-staged/tools.mjs"
import { COMMIT, SOURCE, TAG } from "./pins.mjs"
import { configureArgs } from "./recipe.mjs"

function output(cmd, args) {
  try {
    return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim()
  } catch {
    return null
  }
}

/** Everything this machine lacks to compile it, empty if nothing. audio.cpp requires GCC 13. */
export function missingToolchain() {
  const missing = []
  if (output("cmake", ["--version"]) == null) missing.push(CMAKE)
  if (process.platform === "win32") {
    if (!visualStudio()) missing.push(VISUAL_STUDIO)
    return missing
  }
  const cxx = process.env.CXX ?? "g++"
  const version = output(cxx, ["-dumpversion"])
  if (version == null) missing.push(GCC_13)
  // No package fixes an old one: the distribution's g++ is already installed.
  else if (Number(version.split(".")[0]) < 13) missing.push({ name: `${GCC_13.name} (${cxx} is ${version})` })
  return missing
}

/** Build the server in `work`; returns where its files and its source are. */
export function compile(work) {
  const source = join(work, "source")
  const build = join(work, "build")
  const run = (cmd, args) => execFileSync(cmd, args, { stdio: "inherit" })

  run("git", ["-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1", "--branch", TAG, SOURCE, source])
  const head = output("git", ["-C", source, "rev-parse", "HEAD"])
  if (head !== COMMIT) throw new Error(`audio.cpp ${TAG} is ${head}, not the pinned ${COMMIT}`)

  // Ninja needs MSVC's environment on Windows, so there CMake picks Visual Studio.
  const ninja = process.platform !== "win32" && output("ninja", ["--version"]) != null
  run("cmake", ["-S", source, "-B", build, ...(ninja ? ["-G", "Ninja"] : []), ...configureArgs(process.platform)])
  run("cmake", [
    "--build", build,
    "--config", "Release",
    "--parallel", String(availableParallelism()),
    "--target", "audiocpp_server",
  ])
  return { binaries: build, source }
}
