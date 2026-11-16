import { afterEach, describe, expect, it, vi } from "vitest"

import { browserLocale, LOCALE_KEY } from "./browser-locale"

function browserLanguages(languages: string[]) {
  vi.spyOn(navigator, "languages", "get").mockReturnValue(languages)
}

describe("the browser's locale, without Electron", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it("follows the browser's languages until a language is chosen", async () => {
    browserLanguages(["sv-SE", "ja-JP"])
    expect(await browserLocale.preference()).toBe("system")
    expect(browserLocale.get()).toBe("ja")
  })

  it("keeps a chosen language on this browser, over its own languages", async () => {
    browserLanguages(["ja-JP"])
    await browserLocale.set("de")
    expect(await browserLocale.preference()).toBe("de")
    expect(browserLocale.get()).toBe("de")
    expect(localStorage.getItem(LOCALE_KEY)).toBe("de")
  })

  it("reads an unknown stored choice as system", async () => {
    browserLanguages(["fr-FR"])
    localStorage.setItem(LOCALE_KEY, "klingon")
    expect(await browserLocale.preference()).toBe("system")
    expect(browserLocale.get()).toBe("fr")
  })

  it("tells listeners the language a choice resolves to", async () => {
    browserLanguages(["ko-KR"])
    const listener = vi.fn()
    const stop = browserLocale.onChange(listener)
    await browserLocale.set("es")
    await browserLocale.set("system")
    stop()
    await browserLocale.set("ru")
    expect(listener.mock.calls).toEqual([["es"], ["ko"]])
  })

  it("follows a choice made in another tab", () => {
    browserLanguages(["en-US"])
    const listener = vi.fn()
    const stop = browserLocale.onChange(listener)
    localStorage.setItem(LOCALE_KEY, "hi")
    window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_KEY }))
    stop()
    expect(listener).toHaveBeenCalledWith("hi")
  })

  it("follows the browser's languages when they change", () => {
    browserLanguages(["en-US"])
    const listener = vi.fn()
    const stop = browserLocale.onChange(listener)
    browserLanguages(["pt-PT"])
    window.dispatchEvent(new Event("languagechange"))
    stop()
    expect(listener).toHaveBeenCalledWith("pt-BR")
  })
})
