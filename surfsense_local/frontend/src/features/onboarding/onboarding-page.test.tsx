import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import { OnboardingPage } from "./onboarding-page"

function installApi() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/providers") {
      return Response.json([
        {
          name: "ollama",
          healthy: true,
          can_download: true,
          requires_key: false,
          configured: true,
        },
      ])
    }
    if (path === "/llm/providers/ollama/models") {
      return Response.json([
        {
          name: "llama3.2:1b",
          installed: true,
          capabilities: ["completion"],
        },
      ])
    }
    if (path === "/llm/selection/generation") {
      return Response.json({
        role: "generation",
        provider: "ollama",
        name: "llama3.2:1b",
        updated_at: "2026-09-05T00:00:00Z",
      })
    }
    if (path === "/llm/catalog") {
      return Response.json({
        hardware: {},
        llmfit_version: "1.0",
        recommended: [],
        explore: [],
        installed: [],
        warnings: [],
        runtime_status: {},
      })
    }
    if (init?.method === "PUT") {
      throw new Error("Unexpected selection write")
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("model onboarding", () => {
  it("shows the model tabs and catalog skeleton while selection data loads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined))
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)

    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    expect(screen.getByRole("tab", { name: "Local" })).toBeTruthy()
    expect(
      screen.getByRole("status", { name: "Scanning model catalog" })
    ).toBeTruthy()
    expect(
      document.querySelector('[data-slot="hardware-name-skeleton"]')
    ).toBeTruthy()
    expect(
      document.querySelector('[data-slot="hardware-memory-skeleton"]')
    ).toBeTruthy()
    expect(
      screen.queryByRole("status", { name: "Loading installed models" })
    ).toBeNull()
  })

  it("keeps both provider tabs stable after model data loads", async () => {
    vi.stubGlobal("fetch", installApi())
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)

    expect(
      screen.getByRole("heading", {
        name: "Think across everything you have collected.",
      })
    ).toBeTruthy()
    const firstProgress = screen.getByLabelText("Onboarding step 1 of 2")
    expect(firstProgress.children[0]?.getAttribute("data-state")).toBe("active")
    expect(firstProgress.children[1]?.getAttribute("data-state")).toBe(
      "inactive"
    )
    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    await screen.findByText(
      "Only models compatible with this computer are shown."
    )
    const secondProgress = screen.getByLabelText("Onboarding step 2 of 2")
    expect(secondProgress.children[0]?.getAttribute("data-state")).toBe(
      "completed"
    )
    expect(secondProgress.children[1]?.getAttribute("data-state")).toBe(
      "active"
    )
    const page = screen.getByRole("main")
    const card = document.querySelector('[data-slot="card"]')
    const cardContent = document.querySelector('[data-slot="card-content"]')
    const scrollArea = document.querySelector(
      '[data-slot="scroll-shadow-viewport"]'
    ) as HTMLDivElement
    const topShadow = document.querySelector('[data-slot="scroll-shadow-top"]')
    const bottomShadow = document.querySelector(
      '[data-slot="scroll-shadow-bottom"]'
    )

    expect(page.hasAttribute("data-onboarding-page")).toBe(true)
    expect(page.className).toContain("overflow-hidden")
    expect(card?.className).not.toContain("flex-1")
    expect(card?.className).toContain("h-full")
    expect(card?.className).toContain("gap-0")
    expect(cardContent?.className).toContain("flex-1")
    expect(scrollArea.className).toContain("overflow-y-auto")
    expect(topShadow?.className).toContain("duration-100")
    expect(bottomShadow?.className).toContain("duration-100")
    expect(screen.getByRole("tab", { name: "Local" })).toBeTruthy()
    expect(screen.getByRole("tab", { name: "OpenAI-compatible" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Continue" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Use this model" })).toBeNull()

    Object.defineProperties(scrollArea, {
      clientHeight: { configurable: true, value: 200 },
      scrollHeight: { configurable: true, value: 400 },
      scrollTop: { configurable: true, value: 100, writable: true },
    })
    fireEvent.scroll(scrollArea)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-100")
      expect(bottomShadow?.className).toContain("opacity-100")
    })
  })
})
