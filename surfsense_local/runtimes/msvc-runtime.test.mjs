import assert from "node:assert/strict"
import test from "node:test"

import { generatorName } from "./msvc-runtime.mjs"

test("names each Visual Studio as CMake's generator for it", () => {
  assert.equal(generatorName("17.12.35527.113", "2022"), "Visual Studio 17 2022")
  assert.equal(generatorName("18.0.11010.1", "2026"), "Visual Studio 18 2026")
})

test("Visual Studio 2026's vswhere gives its product line as 18, not the year", () => {
  assert.equal(generatorName("18.0.11010.1", "18"), "Visual Studio 18 2026")
  assert.equal(generatorName("17.14.36414.22", undefined), "Visual Studio 17 2022")
})

test("a Visual Studio whose year is unknown gets no generator", () => {
  assert.equal(generatorName("19.0.1.1", "19"), null)
})
