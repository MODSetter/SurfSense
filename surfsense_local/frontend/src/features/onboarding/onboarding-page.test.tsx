import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
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
  it("keeps the local catalog direct when no remote provider exists", async () => {
    vi.stubGlobal("fetch", installApi())
    render(<OnboardingPage onComplete={() => undefined} />)

    await screen.findByText("Only models compatible with this computer are shown.")
    const page = screen.getByRole("main")
    const card = document.querySelector('[data-slot="card"]')
    const cardContent = document.querySelector('[data-slot="card-content"]')
    const scrollArea = document.querySelector(
      '[data-slot="onboarding-models-scroll"]'
    ) as HTMLDivElement
    const topShadow = document.querySelector(
      '[data-slot="onboarding-models-shadow-top"]'
    )
    const bottomShadow = document.querySelector(
      '[data-slot="onboarding-models-shadow-bottom"]'
    )

    expect(page.hasAttribute("data-onboarding-page")).toBe(true)
    expect(page.className).toContain("overflow-hidden")
    expect(card?.className).not.toContain("flex-1")
    expect(card?.className).toContain("gap-0")
    expect(cardContent?.className).not.toContain("flex-1")
    expect(topShadow?.className).toContain("duration-100")
    expect(bottomShadow?.className).toContain("duration-100")
    expect(screen.queryByRole("tablist")).toBeNull()
    expect(screen.queryByRole("button", { name: "Continue" })).toBeNull()
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
