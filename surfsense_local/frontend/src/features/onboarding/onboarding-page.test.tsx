import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import { OnboardingPage } from "./onboarding-page"

function installApi() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
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
    if (path === "/llm/providers/llamacpp/models") {
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
        provider: "llamacpp",
        name: "llama3.2:1b",
        updated_at: "2026-09-05T00:00:00Z",
      })
    }
    if (path === "/llm/selection/image_generation") {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") {
      return Response.json([])
    }
    if (path === "/llm/onboarding" && init?.method === "POST") {
      return Response.json({ completed: true })
    }
    if (path === "/llm/catalog") {
      return Response.json({
        budget: {
          device_total_bytes: 16_000_000_000,
          device_free_bytes: 14_000_000_000,
          usable_vram_bytes: 12_900_000_000,
          fit_reserve_bytes: 1_073_741_824,
          ram_available_bytes: 16_000_000_000,
          uma: true,
          has_gpu: true,
        },
        curated: [],
        installed: [
          {
            model_id: "Llama 3.2 1B",
            file: "Llama-3.2-1B-Q4_K_M.gguf",
            size_bytes: 1_200_000_000,
            selected: true,
          },
        ],
        recommended_model_id: null,
      })
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
  it("shows the model tabs without a catalog skeleton while selection data loads", async () => {
    // The catalog GET no longer probes hardware on an unrefreshed load, so
    // it's expected to resolve fast enough that no loading state is shown —
    // this pending promise never resolves, confirming nothing renders for it.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined))
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)

    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    expect(screen.getByRole("tab", { name: "Local" })).toBeTruthy()
    expect(
      screen.queryByRole("status", { name: "Scanning model catalog" })
    ).toBeNull()
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
        name: "Air-gapped, open source NotebookLM alternative",
      })
    ).toBeTruthy()
    const firstProgress = screen.getByLabelText("Onboarding step 1 of 2")
    expect(firstProgress.children[0]?.getAttribute("data-state")).toBe("active")
    expect(firstProgress.children[1]?.getAttribute("data-state")).toBe(
      "inactive"
    )
    await user.click(screen.getByRole("button", { name: "Start setting up" }))

    // The catalog no longer filters by fit, so this line stopped describing
    // anything: every model is listed and every one carries an honest badge.
    await screen.findByText(
      "Every model below is priced against this computer."
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
    expect(
      screen.getByRole("button", { name: "Delete Llama 3.2 1B" })
    ).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "Start chatting" })
        .hasAttribute("disabled")
    ).toBe(false)
    expect(
      screen.getByRole("button", { name: "Delete Llama 3.2 1B" })
    ).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Use this model" })).toBeNull()
    expect(
      screen.queryByRole("button", { name: "Use selected model" })
    ).toBeNull()

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

  it("leaves onboarding only after Start chatting, and needs a chat model", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const path = String(input)
      if (path === "/llm/selection/generation") {
        return Response.json({ detail: "not selected" }, { status: 404 })
      }
      if (path === "/llm/selection/image_generation") {
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
      if (path === "/llm/catalog") {
        return Response.json({
          hardware: {},
          curated: [],
          explore: [],
          installed: [],
          scanned: true,
          warnings: [],
          runtime_status: {},
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
