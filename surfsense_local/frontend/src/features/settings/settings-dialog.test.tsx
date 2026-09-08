import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"

import { SettingsDialog } from "./settings-dialog"

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.classList.remove("light", "dark")
  vi.restoreAllMocks()
})

describe("SettingsDialog", () => {
  it("changes and persists the appearance preference", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <SettingsDialog open onOpenChange={() => undefined} />
      </ThemeProvider>
    )

    expect(screen.getByRole("heading", { name: "General" }).textContent).toBe(
      "General"
    )

    await user.click(screen.getByRole("radio", { name: /^Dark/ }))

    expect(localStorage.getItem("theme")).toBe("dark")
    await waitFor(() =>
      expect(document.documentElement.classList.contains("dark")).toBe(true)
    )
  })
})
