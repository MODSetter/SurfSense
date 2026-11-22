import { describe, expect, it } from "vitest"

import { resolveLocale } from "./resolve-locale"

// The same cases as electron/src/main/i18n/resolve-locale.test.ts: the desktop
// and a browser must pick the same catalog for the same languages.
describe("resolveLocale", () => {
  it("an explicit choice wins over the system languages", () => {
    expect(resolveLocale("de", ["ja-JP", "en-US"])).toBe("de")
  })

  it("system follows the first supported system language by its base", () => {
    expect(resolveLocale("system", ["sv-SE", "ja-JP", "de-DE"])).toBe("ja")
  })

  it("system falls back to English when no system language is supported", () => {
    expect(resolveLocale("system", ["sv-SE", "nl-NL"])).toBe("en")
  })

  it("any Portuguese system gets the Brazilian catalog", () => {
    expect(resolveLocale("system", ["pt-PT"])).toBe("pt-BR")
    expect(resolveLocale("system", ["pt-BR"])).toBe("pt-BR")
  })

  it("a Simplified Chinese system gets the Simplified catalog", () => {
    for (const tag of ["zh-CN", "zh-Hans-CN", "zh-SG", "zh-Hans", "zh"]) {
      expect(resolveLocale("system", [tag]), tag).toBe("zh-CN")
    }
  })

  it("a Traditional Chinese system falls through, since no catalog is Traditional", () => {
    expect(resolveLocale("system", ["zh-TW", "ja-JP"])).toBe("ja")
    for (const tag of ["zh-Hant-TW", "zh-HK", "zh-MO", "zh-Hant"]) {
      expect(resolveLocale("system", [tag]), tag).toBe("en")
    }
  })

  it("an explicit region-tagged choice is kept", () => {
    expect(resolveLocale("pt-BR", ["en-US"])).toBe("pt-BR")
  })

  it("an unknown stored choice is treated as system", () => {
    expect(resolveLocale("klingon", ["de-AT"])).toBe("de")
  })
})
