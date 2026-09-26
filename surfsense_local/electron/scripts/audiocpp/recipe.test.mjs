import assert from "node:assert/strict"
import test from "node:test"

import { FAMILIES } from "./pins.mjs"
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

for (const platform of ["linux", "win32"]) {
  test(`${platform}: builds the CPU backend only`, () => {
    // The GPU is the chat model's; a GPU backend would ship unused and ggml
    // would still load it, and Vulkan alone was 329 of 836 build steps.
    const defs = definitions(configureArgs(platform))
    for (const backend of ["CUDA", "HIP", "VULKAN", "METAL"]) {
      assert.equal(defs.get(`ENGINE_ENABLE_${backend}`), "OFF", backend)
    }
  })

  test(`${platform}: one CPU library per micro-architecture, not the build machine's`, () => {
    // A build for the machine it ran on stops with an illegal instruction on an
    // older CPU; upstream's Windows server carries 7,264 AVX-512 instructions.
    const defs = definitions(configureArgs(platform))
    assert.equal(defs.get("ENGINE_ENABLE_NATIVE_CPU"), "OFF")
    assert.equal(defs.get("ENGINE_ENABLE_CPU_ALL_VARIANTS"), "ON")
  })

  test(`${platform}: ships no OpenMP runtime`, () => {
    const defs = definitions(configureArgs(platform))
    assert.equal(defs.get("ENGINE_ENABLE_OPENMP"), "OFF")
    assert.equal(defs.get("GGML_OPENMP"), "OFF")
  })

  test(`${platform}: builds only the curated model families`, () => {
    const defs = definitions(configureArgs(platform))
    assert.equal(defs.get("AUDIOCPP_MODEL_SET"), "custom")
    assert.equal(defs.get("AUDIOCPP_MODELS"), FAMILIES.join(","))
  })
}

test("linux: links libstdc++ into every file, ggml's backend modules included", () => {
  // Measured: the backends are CMake modules, which ignore the shared flags,
  // and linked dynamically they need GCC 13's libstdc++, which 22.04 lacks.
  const defs = definitions(configureArgs("linux"))
  for (const kind of ["EXE", "SHARED", "MODULE"]) {
    assert.match(defs.get(`CMAKE_${kind}_LINKER_FLAGS`) ?? "", /-static-libstdc\+\+/, kind)
  }
})

test("linux: leaves libgcc dynamic", () => {
  // Measured: GCC 13's static unwinder on 22.04 calls _dl_find_object, glibc 2.35.
  assert.ok(!configureArgs("linux").some((arg) => arg.includes("-static-libgcc")))
})

test("win32: targets x64 and leaves the MSVC runtime dynamic", () => {
  const args = configureArgs("win32")
  assert.deepEqual(args.slice(args.indexOf("-A"), args.indexOf("-A") + 2), ["-A", "x64"])
  assert.ok(!args.some((arg) => arg.includes("LINKER_FLAGS")))
})
