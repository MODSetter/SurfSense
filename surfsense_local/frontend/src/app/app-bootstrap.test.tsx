import { act, cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"
import { AppBootstrap } from "./app-bootstrap"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("app bootstrap", () => {
  it("shows an animated ASCII loader while startup is pending", () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {}))
    )

    render(
      <TooltipProvider>
        <AppBootstrap />
      </TooltipProvider>
    )

    expect(
      screen.getByRole("status", { name: "Starting SurfSense" }).textContent
    ).toBe("[|]")
    act(() => vi.advanceTimersByTime(120))
    expect(screen.getByRole("status").textContent).toBe("[/]")
  })

  it("shows onboarding only before it has been completed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/onboarding") {
          return Response.json({ completed: false })
        }
        if (path === "/llm/providers") {
          return Response.json([])
        }
        if (path === "/llm/selection/generation") {
          return Response.json({ detail: "not found" }, { status: 404 })
        }
        if (path === "/llm/catalog") {
          return Response.json({
            hardware: null,
            llmfit_version: null,
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

    render(<AppBootstrap />)

    expect(
      await screen.findByRole("heading", {
        name: "Your research, ready to answer",
      })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Next" })).toBeTruthy()
    expect(screen.queryByText("Choose your AI model")).toBeNull()
    expect(screen.getByRole("main").hasAttribute("data-onboarding-page")).toBe(
      true
    )
  })

  it("keeps completed users in the dashboard without a model", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    )
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/onboarding") {
          return Response.json({ completed: true })
        }
        if (path === "/llm/providers") {
          return Response.json([])
        }
        if (path === "/llm/selection/generation") {
          return Response.json({ detail: "not found" }, { status: 404 })
        }
        if (path === "/workspaces") {
          return Response.json([
            {
              id: 1,
              name: "Research",
              created_at: "2026-09-09T00:00:00Z",
              updated_at: "2026-09-09T00:00:00Z",
            },
          ])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([
            {
              id: 10,
              workspace_id: 1,
              title: "Existing chat",
              created_at: "2026-09-09T00:00:00Z",
              updated_at: "2026-09-09T00:00:00Z",
            },
          ])
        }
        if (
          path ===
            "/workspaces/1/documents?document_type=FILE&document_type=NOTE" ||
          path === "/chat/threads/10/messages"
        ) {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )

    render(
      <TooltipProvider>
        <AppBootstrap />
      </TooltipProvider>
    )

    const setup = await screen.findByRole(
      "button",
      { name: "Set up model" },
      { timeout: 10_000 }
    )
    expect(setup.querySelector("svg")).toBeNull()
    expect(setup.className).toContain("text-[11px]")
    expect(setup.className).toContain("px-1.5")
    expect(setup.className).toContain("py-1")
    expect(setup.className).toContain("text-white")
    const message = screen.getByRole("textbox", { name: "Message" })
    expect((message as HTMLTextAreaElement).disabled).toBe(true)
    expect(message.getAttribute("placeholder")).toBe("Follow up on this answer")
    expect(
      screen.getByText("SurfSense can make mistakes. Check important answers.")
    ).toBeTruthy()
    expect(screen.queryByText("No chat model is available")).toBeNull()
    expect(screen.queryByText("Choose your AI model")).toBeNull()
  }, 15_000)
})
