import assert from "node:assert/strict"
import test from "node:test"

import { resolveLocale } from "./resolve-locale.ts"

test("an explicit choice wins over the system languages", () => {
  assert.equal(resolveLocale("de", ["ja-JP", "en-US"]), "de")
})

test("system follows the first supported system language by its base", () => {
  assert.equal(resolveLocale("system", ["fr-FR", "ja-JP", "de-DE"]), "ja")
})

test("system falls back to English when no system language is supported", () => {
  assert.equal(resolveLocale("system", ["fr-FR", "zh-Hans-CN"]), "en")
})

test("an unknown stored choice is treated as system", () => {
  assert.equal(resolveLocale("klingon", ["de-AT"]), "de")
})
