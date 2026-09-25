import assert from "node:assert/strict"
import test from "node:test"

import { configureArgs } from "./recipe.mjs"

/** The -D definitions in a configure command, as a name-to-value map. */
function definitions(args) {
  return new Map(
    args
      .filter((arg) => arg.startsWith("-D"))
      .map((arg) => {
        const [name, ...value] = arg.slice(2).split("=")
        return [name, value.join("=")]
      })
  )
}

for (const platform of ["linux", "darwin"]) {
  test(`${platform}: writes WebM clips and WebP images, and skips the web page`, () => {
    // A missing submodule would otherwise turn WebM off without a word.
    const defs = definitions(configureArgs(platform))
    assert.equal(defs.get("SD_WEBP"), "ON")
    assert.equal(defs.get("SD_WEBM"), "ON")
    assert.equal(defs.get("SD_SERVER_BUILD_FRONTEND"), "OFF")
  })
}

test("linux: runs on the GPU through Vulkan", () => {
  // A diffusion model on the CPU takes minutes an image.
  assert.equal(definitions(configureArgs("linux")).get("SD_VULKAN"), "ON")
})

test("linux: one CPU library per micro-architecture, not the build machine's", () => {
  // A build for the machine it ran on stops with an illegal instruction on an
  // older CPU.
  const defs = definitions(configureArgs("linux"))
  assert.equal(defs.get("GGML_NATIVE"), "OFF")
  assert.equal(defs.get("GGML_BACKEND_DL"), "ON")
  assert.equal(defs.get("GGML_CPU_ALL_VARIANTS"), "ON")
})

test("linux: ships no OpenMP runtime", () => {
  // Upstream's Linux build needs libgomp, which not every system has.
  assert.equal(definitions(configureArgs("linux")).get("GGML_OPENMP"), "OFF")
})

test("linux: links libstdc++ into every file, ggml's backend modules included", () => {
  // Upstream's build needs GLIBCXX_3.4.32, newer than 22.04's.
  const defs = definitions(configureArgs("linux"))
  for (const kind of ["EXE", "SHARED", "MODULE"]) {
    assert.match(defs.get(`CMAKE_${kind}_LINKER_FLAGS`) ?? "", /-static-libstdc\+\+/, kind)
  }
  assert.ok(!configureArgs("linux").some((arg) => arg.includes("-static-libgcc")))
})

test("linux: finds its libraries beside the server", () => {
  const defs = definitions(configureArgs("linux"))
  assert.equal(defs.get("CMAKE_BUILD_WITH_INSTALL_RPATH"), "ON")
  assert.equal(defs.get("CMAKE_INSTALL_RPATH"), "$ORIGIN")
})

test("darwin: runs on Metal, with its shaders inside the library", () => {
  const defs = definitions(configureArgs("darwin"))
  assert.equal(defs.get("SD_METAL"), "ON")
  assert.equal(defs.get("GGML_METAL_EMBED_LIBRARY"), "ON")
})

test("darwin: runs on macOS 13.3, the floor llama.cpp's and audio.cpp's builds set", () => {
  // Upstream's archive is built for macOS 26.0 and would not start before it.
  const defs = definitions(configureArgs("darwin"))
  assert.equal(defs.get("CMAKE_OSX_DEPLOYMENT_TARGET"), "13.3")
  assert.equal(defs.get("CMAKE_OSX_ARCHITECTURES"), "arm64")
})

test("darwin: finds its library beside the server", () => {
  const defs = definitions(configureArgs("darwin"))
  assert.equal(defs.get("CMAKE_BUILD_WITH_INSTALL_RPATH"), "ON")
  assert.equal(defs.get("CMAKE_INSTALL_RPATH"), "@loader_path")
})
