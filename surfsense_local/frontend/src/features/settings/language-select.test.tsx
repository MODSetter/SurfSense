import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

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

  it("lists each language in its own name, after the system option", () => {
    fakeBridge("system")
    render(<LanguageSelect aria-label="Language" />)
    const options = screen
      .getAllByRole("option")
      .map((option) => option.textContent)
    // Tests run as a dev build, which also lists the pseudo-locale.
    expect(options).toEqual([
      "Match system",
      "English",
      "日本語",
      "Deutsch",
      "English (Pseudo-Accents)",
    ])
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
