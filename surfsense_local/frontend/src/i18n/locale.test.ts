import { afterEach, describe, expect, it, vi } from "vitest"

function fakeBridge(initial: string) {
  let listener: ((locale: string) => void) | undefined
  window.surfsense = {
    locale: {
      get: () => initial,
      preference: async () => "system",
      set: async () => {},
      onChange: (next: (locale: string) => void) => {
        listener = next
        return () => (listener = undefined)
      },
    },
  } as unknown as Window["surfsense"]
  return { change: (locale: string) => listener?.(locale) }
}

// intl is built once per page, from what preload reports at load.
async function loadPage() {
  vi.resetModules()
  const { intl } = await import("./intl")
  const { followLocale } = await import("./locale")
  return { intl, followLocale }
}

describe("the page's language", () => {
  afterEach(() => {
    window.surfsense = undefined
  })

  it("starts in the language main reports and sets <html lang>", async () => {
    fakeBridge("ja")
    const { intl, followLocale } = await loadPage()
    followLocale(() => {})
    expect(intl.locale).toBe("ja")
    expect(document.documentElement.lang).toBe("ja")
    expect(intl.formatMessage({ id: "app_bootstrap_retry_button" })).toBe(
      "再試行"
    )
  })

  it("falls back to English for a language the app does not ship", async () => {
    // Swedish, as in resolve-locale.test.ts: a language with no catalog.
    fakeBridge("sv")
    const { intl } = await loadPage()
    expect(intl.locale).toBe("en")
  })

  it("starts in the browser's language without the Electron bridge", async () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["de-AT"])
    const { intl } = await loadPage()
    expect(intl.locale).toBe("de")
    vi.restoreAllMocks()
  })

  it("reloads without the Electron bridge when a language is chosen", async () => {
    const { followLocale } = await loadPage()
    const { browserLocale } = await import("./browser-locale")
    const reload = vi.fn()
    followLocale(reload)
    await browserLocale.set("ja")
    localStorage.clear()
    expect(reload).toHaveBeenCalledOnce()
  })

  it("stays in English without the Electron bridge", async () => {
    const { intl } = await loadPage()
    expect(intl.formatMessage({ id: "app_bootstrap_retry_button" })).toBe(
      "Retry"
    )
  })

  it("reloads the window when main switches to another language", async () => {
    const bridge = fakeBridge("en")
    const { followLocale } = await loadPage()
    const reload = vi.fn()
    followLocale(reload)
    bridge.change("en")
    expect(reload).not.toHaveBeenCalled()
    bridge.change("de")
    expect(reload).toHaveBeenCalledOnce()
  })
})
