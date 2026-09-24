import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { THEME_STORAGE_KEY, ThemeProvider } from "@/components/theme-provider"
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

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")
    await waitFor(() =>
      expect(document.documentElement.classList.contains("dark")).toBe(true)
    )
  })

  it("shows each model type as its own section", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([])
        }
        if (path === "/llm/selection/text_gen") {
          return Response.json({
            model_type: "text_gen",
            provider: "llamacpp",
            name: "qwen3:1.7b",
            updated_at: "2026-09-09T00:00:00Z",
          })
        }
        if (path === "/llm/selection/image_gen") {
          return Response.json({
            model_type: "image_gen",
            provider: "openai_compatible",
            connection_id: 9,
            name: "flux",
            updated_at: "2026-09-09T00:00:00Z",
          })
        }
        if (path === "/llm/selection/audio_gen") {
          return Response.json({
            model_type: "audio_gen",
            provider: "openai_compatible",
            connection_id: 9,
            name: "tts-1",
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
        if (path === "/llm/catalog/local") {
          return Response.json({
            rows: [],
            recommended_id: null,
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(<SettingsHarness />)
    await user.click(screen.getByRole("button", { name: "Chat" }))

    expect(
      await screen.findByRole("heading", { name: "Text generation models" })
    ).toBeTruthy()
    // The model in use is named even when no local file answers to it.
    const chat = await screen.findByRole("region", {
      name: "chat model in use",
    })
    await waitFor(() => expect(chat.textContent).toContain("qwen3:1.7b"))
    expect(chat.textContent).toContain("Not found on this computer")
    const scrollViewport = document.querySelector(
      '[data-slot="scroll-shadow-viewport"]'
    )
    expect(scrollViewport?.className).toContain("overflow-y-auto")
    // The heading scrolls with the rest of the section: its content varies
    // too much in height for a fixed header to make sense.
    expect(
      scrollViewport?.contains(
        screen.getByRole("heading", { name: "Text generation models" })
      )
    ).toBe(true)

    await user.click(screen.getByRole("button", { name: "Image" }))

    expect(
      await screen.findByRole("heading", { name: "Image generation models" })
    ).toBeTruthy()
    const image = await screen.findByRole("region", {
      name: "image model in use",
    })
    await waitFor(() => expect(image.textContent).toContain("flux"))
    expect(image.textContent).toContain("openrouter test")

    await user.click(screen.getByRole("button", { name: "Audio" }))

    expect(
      await screen.findByRole("heading", { name: "Audio generation models" })
    ).toBeTruthy()
    const audio = await screen.findByRole("region", {
      name: "audio model in use",
    })
    await waitFor(() => expect(audio.textContent).toContain("tts-1"))
  })

  it("shows nothing half-loaded while model data loads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined))
    )
    const user = userEvent.setup()

    render(<SettingsHarness />)
    await user.click(screen.getByRole("button", { name: "Chat" }))

    expect(
      screen.getByRole("heading", { name: "Text generation models" })
    ).toBeTruthy()
    expect(screen.queryByText("No chat model yet")).toBeNull()
    expect(screen.queryByRole("status")).toBeNull()
  })
})
