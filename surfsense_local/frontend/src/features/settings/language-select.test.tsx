import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { SELECTABLE_LOCALES } from "@/i18n/locales"
import { LanguageSelect } from "./language-select"

function fakeBridge(preference: string) {
  const set = vi.fn(async () => {})
  window.surfsense = {
    locale: {
      get: () => "en",
      preference: async () => preference,
      set,
      onChange: () => () => {},
    },
  } as unknown as Window["surfsense"]
  return { set }
}

describe("LanguageSelect", () => {
  afterEach(() => {
    cleanup()
    window.surfsense = undefined
  })

  it("offers every shipped language, after the system option", () => {
    fakeBridge("system")
    render(<LanguageSelect aria-label="Language" />)
    const values = screen
      .getAllByRole<HTMLOptionElement>("option")
      .map((option) => option.value)
    // Tests run as a dev build, which also lists the pseudo-locale.
    expect(values).toEqual(["system", ...SELECTABLE_LOCALES])
  })

  it("names each language in its own language, not in English", () => {
    fakeBridge("system")
    render(<LanguageSelect aria-label="Language" />)
    const labels = screen
      .getAllByRole("option")
      .map((option) => option.textContent)
    // A sample, so a new language needs no edit here: the point is that the
    // label comes from the language itself, so someone in the wrong one can
    // still find theirs.
    expect(labels).toEqual(expect.arrayContaining(["日本語", "Deutsch"]))
  })

  it("shows the saved preference", async () => {
    fakeBridge("de")
    render(<LanguageSelect aria-label="Language" />)
    await waitFor(() =>
      expect(screen.getByRole<HTMLSelectElement>("combobox").value).toBe("de")
    )
  })

  it("hands the choice to main", async () => {
    const { set } = fakeBridge("system")
    render(<LanguageSelect aria-label="Language" />)
    await userEvent.selectOptions(screen.getByRole("combobox"), "ja")
    expect(set).toHaveBeenCalledWith("ja")
  })
})
