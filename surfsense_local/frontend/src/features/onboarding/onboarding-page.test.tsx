import { cleanup, screen } from "@testing-library/react"
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

    expect(page.hasAttribute("data-onboarding-page")).toBe(true)
    expect(page.className).toContain("overflow-hidden")
    expect(screen.queryByRole("tablist")).toBeNull()
    expect(screen.queryByRole("button", { name: "Continue" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Use this model" })).toBeNull()
  })
})
