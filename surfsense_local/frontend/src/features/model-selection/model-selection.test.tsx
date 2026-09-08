import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"
import { ModelSelectionPage } from "./model-selection-page"

function installApi(modelInstalled: boolean) {
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
      return Response.json(
        modelInstalled
          ? [
              {
                name: "llama3.2:1b",
                installed: true,
                capabilities: ["completion"],
              },
            ]
          : []
      )
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

describe("model selection", () => {
  it("keeps page actions outside the scrollable model panel", async () => {
    vi.stubGlobal("fetch", installApi(true))
    render(<ModelSelectionPage />)

    const panel = await screen.findByRole("tabpanel")
    const continueButton = screen.getByRole("button", { name: "Continue" })

    expect(screen.getByRole("main").className).toContain("overflow-hidden")
    expect(screen.getByRole("main").className).toContain("select-none")
    expect(panel.className).toContain("overflow-y-auto")
    expect(panel.contains(continueButton)).toBe(false)
  })

  it("continues with an already validated selection without writing", async () => {
    const fetchMock = installApi(true)
    vi.stubGlobal("fetch", fetchMock)
    const onSelected = vi.fn()
    const user = userEvent.setup()

    render(<ModelSelectionPage onSelected={onSelected} />)
    await user.click(await screen.findByRole("button", { name: "Continue" }))

    expect(onSelected).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "ollama", name: "llama3.2:1b" })
    )
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")
    ).toBe(false)
  })

  it("blocks a persisted selection that is no longer installed", async () => {
    vi.stubGlobal("fetch", installApi(false))
    render(<ModelSelectionPage />)

    expect(
      await screen.findByText("Your previous model is no longer available")
    ).toBeTruthy()
    expect(
      (screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
  })
})
