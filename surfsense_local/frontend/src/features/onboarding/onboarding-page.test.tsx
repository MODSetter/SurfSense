import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import { OnboardingPage } from "./onboarding-page"

function installApi() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/selection/text_gen") {
      return Response.json({
        model_type: "text_gen",
        provider: "llamacpp",
        name: "llama3.2:1b",
        updated_at: "2026-09-05T00:00:00Z",
      })
    }
    if (path === "/llm/selection/image_gen") {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") {
      return Response.json([])
    }
    if (path === "/llm/onboarding" && init?.method === "POST") {
      return Response.json({ completed: true })
    }
    if (init?.method === "PUT") {
      throw new Error("Unexpected selection write")
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

beforeEach(() => {
  // The welcome step mounts OnboardingDither, which reads matchMedia.
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
  vi.unstubAllGlobals()
})

describe("model onboarding", () => {
  it("moves from the welcome to the model step", async () => {
    vi.stubGlobal("fetch", installApi())
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)

    expect(
      screen.getByRole("heading", {
        name: "Air-gapped, open source NotebookLM alternative",
      })
    ).toBeTruthy()
    const firstProgress = screen.getByLabelText("Onboarding step 1 of 2")
    expect(firstProgress.children[0]?.getAttribute("data-state")).toBe("active")
    expect(firstProgress.children[1]?.getAttribute("data-state")).toBe(
      "inactive"
    )
    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    expect(
      screen.getByRole("heading", { name: "Choose your AI model" })
    ).toBeTruthy()
    const secondProgress = screen.getByLabelText("Onboarding step 2 of 2")
    expect(secondProgress.children[0]?.getAttribute("data-state")).toBe(
      "completed"
    )
    expect(secondProgress.children[1]?.getAttribute("data-state")).toBe(
      "active"
    )
    const page = screen.getByRole("main")
    const card = document.querySelector('[data-slot="card"]')
    expect(page.hasAttribute("data-onboarding-page")).toBe(true)
    expect(page.className).toContain("overflow-hidden")
    expect(card?.className).toContain("h-full")
  })

  it("leaves onboarding only after Start chatting, and needs a chat model", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const path = String(input)
      if (path === "/llm/selection/text_gen") {
        return Response.json({ detail: "not selected" }, { status: 404 })
      }
      if (path === "/llm/selection/image_gen") {
        return Response.json({ detail: "not selected" }, { status: 404 })
      }
      if (path === "/llm/connections") return Response.json([])
      if (path === "/llm/providers") {
        return Response.json([
          {
            name: "llamacpp",
            healthy: true,
            can_download: true,
            requires_key: false,
            configured: true,
          },
        ])
      }
      if (path === "/llm/providers/llamacpp/models") return Response.json([])
      if (path === "/llm/catalog/local") {
        return Response.json({
          rows: [],
          recommended_id: null,
        })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const onComplete = vi.fn()
    render(<OnboardingPage onComplete={onComplete} />)
    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    expect(
      (
        await screen.findByRole("button", { name: "Start chatting" })
      ).hasAttribute("disabled")
    ).toBe(true)
    expect(onComplete).not.toHaveBeenCalled()
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) => path === "/llm/onboarding" && init?.method === "POST"
      )
    ).toBe(false)
  })

  it("posts onboarding completion when Start chatting is pressed", async () => {
    const fetchMock = installApi()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const onComplete = vi.fn()
    render(<OnboardingPage onComplete={onComplete} />)
    await user.click(screen.getByRole("button", { name: "Start setting up" }))
    await user.click(
      await screen.findByRole("button", { name: "Start chatting" })
    )
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce())
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) => path === "/llm/onboarding" && init?.method === "POST"
      )
    ).toBe(true)
  })
})
