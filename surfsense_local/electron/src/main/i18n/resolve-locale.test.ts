import assert from "node:assert/strict"
import test from "node:test"

import { resolveLocale } from "./resolve-locale.ts"

test("an explicit choice wins over the system languages", () => {
  assert.equal(resolveLocale("de", ["ja-JP", "en-US"]), "de")
})

test("system follows the first supported system language by its base", () => {
  assert.equal(resolveLocale("system", ["sv-SE", "ja-JP", "de-DE"]), "ja")
})

test("system falls back to English when no system language is supported", () => {
  assert.equal(resolveLocale("system", ["sv-SE", "nl-NL"]), "en")
})

test("any Portuguese system gets the Brazilian catalog", () => {
  assert.equal(resolveLocale("system", ["pt-PT"]), "pt-BR")
  assert.equal(resolveLocale("system", ["pt-BR"]), "pt-BR")
})

test("a Simplified Chinese system gets the Simplified catalog", () => {
  for (const tag of ["zh-CN", "zh-Hans-CN", "zh-SG", "zh-Hans", "zh"]) {
    assert.equal(resolveLocale("system", [tag]), "zh-CN", tag)
  }
})

test("a Traditional Chinese system falls through, since no catalog is Traditional", () => {
  assert.equal(resolveLocale("system", ["zh-TW", "ja-JP"]), "ja")
  for (const tag of ["zh-Hant-TW", "zh-HK", "zh-MO", "zh-Hant"]) {
    assert.equal(resolveLocale("system", [tag]), "en", tag)
  }
})

test("an explicit region-tagged choice is kept", () => {
  assert.equal(resolveLocale("pt-BR", ["en-US"]), "pt-BR")
})

test("an unknown stored choice is treated as system", () => {
  assert.equal(resolveLocale("klingon", ["de-AT"]), "de")
})
