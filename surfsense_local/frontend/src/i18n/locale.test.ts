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
  const { followMainLocale } = await import("./locale")
  return { intl, followMainLocale }
}

describe("the page's language", () => {
  afterEach(() => {
    window.surfsense = undefined
  })

  it("starts in the language main reports and sets <html lang>", async () => {
    fakeBridge("ja")
    const { intl, followMainLocale } = await loadPage()
    followMainLocale(() => {})
    expect(intl.locale).toBe("ja")
    expect(document.documentElement.lang).toBe("ja")
    expect(intl.formatMessage({ id: "app_bootstrap_retry_button" })).toBe(
      "再試行"
    )
  })

  it("falls back to English for a language the app does not ship", async () => {
    fakeBridge("fr")
    const { intl } = await loadPage()
    expect(intl.locale).toBe("en")
  })

  it("stays in English without the Electron bridge", async () => {
    const { intl } = await loadPage()
    expect(intl.formatMessage({ id: "app_bootstrap_retry_button" })).toBe(
      "Retry"
    )
  })

  it("reloads the window when main switches to another language", async () => {
    const bridge = fakeBridge("en")
    const { followMainLocale } = await loadPage()
    const reload = vi.fn()
    followMainLocale(reload)
    bridge.change("en")
    expect(reload).not.toHaveBeenCalled()
    bridge.change("de")
    expect(reload).toHaveBeenCalledOnce()
  })
})
