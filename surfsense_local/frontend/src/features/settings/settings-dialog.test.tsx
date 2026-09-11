import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { SettingsDialog, type SettingsSectionId } from "./settings-dialog"

function SettingsHarness() {
  const [section, setSection] = useState<SettingsSectionId>("general")
  return (
    <ThemeProvider>
      <TooltipProvider>
        <SettingsDialog
          open
          section={section}
          onOpenChange={() => undefined}
          onSectionChange={setSection}
          onModelSelected={() => undefined}
        />
      </TooltipProvider>
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
      '[data-slot="scroll-shadow-viewport"]'
    )
    const scrollArea = scrollRegion as HTMLDivElement
    expect(scrollRegion?.className).toContain("min-h-0")
    expect(scrollRegion?.className).toContain("overflow-y-auto")
    const topShadow = document.querySelector('[data-slot="scroll-shadow-top"]')
    const bottomShadow = document.querySelector(
      '[data-slot="scroll-shadow-bottom"]'
    )
    expect(topShadow?.className).toContain("duration-100")
    expect(bottomShadow?.className).toContain("duration-100")
    Object.defineProperties(scrollRegion, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, value: 800 },
      scrollTop: { configurable: true, value: 0, writable: true },
    })
    fireEvent.scroll(scrollArea)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-0")
      expect(bottomShadow?.className).toContain("opacity-100")
    })
    scrollArea.scrollTop = 400
    fireEvent.scroll(scrollArea)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-100")
      expect(bottomShadow?.className).toContain("opacity-0")
    })

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
        if (path === "/llm/selection/image_generation") {
          return Response.json({
            role: "image_generation",
            provider: "openai_compatible",
            connection_id: 9,
            name: "flux",
            updated_at: "2026-09-09T00:00:00Z",
          })
        }
        if (path === "/llm/connections") {
          return Response.json([
            {
              id: 9,
              label: "openrouter test",
              provider: "openai_compatible",
              base_url: "https://openrouter.ai/api/v1",
              has_api_key: true,
              created_at: "2026-09-09T00:00:00Z",
              updated_at: "2026-09-09T00:00:00Z",
            },
          ])
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
    expect(screen.queryByText("Currently using")).toBeNull()

    const roles = await screen.findByRole("region", { name: "Models in use" })
    expect(roles.textContent).toContain("qwen3:1.7b")
    expect(roles.textContent).toContain("Local")
    expect(roles.textContent).toContain("flux")
    expect(roles.textContent).toContain("openrouter test")

    expect(screen.getByRole("tab", { name: "Local" })).toBeTruthy()
    expect(screen.getByRole("tab", { name: "OpenAI-compatible" })).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Use selected model" })
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="settings-section-content"]')
        ?.className
    ).toContain("overflow-hidden")
    expect(
      document.querySelector('[data-slot="scroll-shadow-viewport"]')?.className
    ).toContain("overflow-y-auto")
    expect(
      await screen.findByText("No local models are available")
    ).toBeTruthy()
  })

  it("shows the model tabs and catalog skeleton while selection data loads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined))
    )
    const user = userEvent.setup()

    render(<SettingsHarness />)
    await user.click(screen.getByRole("button", { name: "Models" }))

    expect(screen.getByRole("heading", { name: "Models" })).toBeTruthy()
    const roles = screen.getByRole("region", { name: "Models in use" })
    expect(roles.querySelectorAll("[data-slot=skeleton]")).toHaveLength(2)
    expect(screen.queryByText("Loading…")).toBeNull()
    expect(screen.getByRole("tab", { name: "Local" })).toBeTruthy()
    expect(
      screen.getByRole("status", { name: "Scanning model catalog" })
    ).toBeTruthy()
    expect(
      screen.queryByRole("status", { name: "Loading model settings" })
    ).toBeNull()
  })
})
