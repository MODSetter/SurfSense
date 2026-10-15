import assert from "node:assert/strict"
import test from "node:test"

import { generatorName } from "./msvc-runtime.mjs"

test("names each Visual Studio as CMake's generator for it", () => {
  assert.equal(generatorName("17.12.35527.113", "2022"), "Visual Studio 17 2022")
  assert.equal(generatorName("18.0.11010.1", "2026"), "Visual Studio 18 2026")
})
