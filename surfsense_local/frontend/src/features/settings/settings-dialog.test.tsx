import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { render } from "@/test-utils"

import { SettingsDialog, type SettingsSectionId } from "./settings-dialog"

function SettingsHarness() {
  const [section, setSection] = useState<SettingsSectionId>("general")
  return (
    <ThemeProvider>
      <SettingsDialog
        open
        section={section}
        onOpenChange={() => undefined}
        onSectionChange={setSection}
        onModelSelected={() => undefined}
      />
    </ThemeProvider>
  )
}

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

    render(<SettingsHarness />)

    expect(
      screen.getByRole("heading", { name: "Appearance" }).textContent
    ).toBe("Appearance")
    const scrollRegion = document.querySelector(
      '[data-slot="settings-section-scroll"]'
    )
    expect(scrollRegion?.className).toContain("min-h-0")
    expect(scrollRegion?.className).toContain("overflow-y-auto")

    await user.click(
      screen.getByRole("radio", { name: "Switch to dark theme" })
    )

    expect(localStorage.getItem("theme")).toBe("dark")
    await waitFor(() =>
      expect(document.documentElement.classList.contains("dark")).toBe(true)
    )
  })

  it("opens model management inside settings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([])
        }
        if (path === "/llm/selection/generation") {
          return Response.json({
            role: "generation",
            provider: "ollama",
            name: "qwen3:1.7b",
            updated_at: "2026-09-09T00:00:00Z",
          })
        }
        if (path === "/llm/catalog") {
          return Response.json({
            hardware: null,
            llmfit_version: "1.1.11",
            recommended: [],
            explore: [],
            installed: [],
            warnings: [],
            runtime_status: {},
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(<SettingsHarness />)
    await user.click(screen.getByRole("button", { name: "Models" }))

    expect(await screen.findByRole("heading", { name: "Models" })).toBeTruthy()
    expect(screen.getByText("Currently using")).toBeTruthy()
    expect(screen.getByText("qwen3:1.7b")).toBeTruthy()
    expect(
      await screen.findByText("No local models are available")
    ).toBeTruthy()
  })
})
