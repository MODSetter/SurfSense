import { cleanup, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import {
  expectsDashboard,
  rememberDashboard,
} from "@/features/startup/dashboard-hint"
import { render } from "@/test-utils"
import { AppBootstrap } from "./app-bootstrap"

const STARTING = { name: "Starting SurfSense" }

function onDatabase(identity: string) {
  window.surfsense = {
    apiUrl: "",
    databaseIdentity: () => identity,
  } as unknown as Window["surfsense"]
}

function pendingStartup() {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => {}))
  )
}

// A completed install with one workspace and no model; `onboardingAfterMs`
// holds the first answer back, as a slow start does.
function completedInstall({ onboardingAfterMs = 0 } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/onboarding") {
        await new Promise((resolve) => setTimeout(resolve, onboardingAfterMs))
        return Response.json({ completed: true })
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
      if (
        path === "/llm/providers" ||
        path === "/workspaces/1/chat/threads" ||
        path === "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
      ) {
        return Response.json([])
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
}

function renderApp() {
  render(
    <TooltipProvider>
      <AppBootstrap />
    </TooltipProvider>
  )
}

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  // Onboarding's welcome step reads matchMedia.
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
  window.surfsense = undefined
  localStorage.clear()
})

describe("startup screen", () => {
  it("is blank until onboarding has been seen done on this database", () => {
    onDatabase("a")
    pendingStartup()
    renderApp()

    const screenBox = screen.getByRole("status", STARTING)
    expect(screenBox.textContent).toBe("")
    expect(within(screenBox).queryByRole("heading")).toBeNull()
  })

  it("is blank without the desktop, whose data can change under the browser", () => {
    rememberDashboard()
    pendingStartup()
    renderApp()

    expect(screen.getByRole("status", STARTING).textContent).toBe("")
  })

  it("draws the dashboard's constant parts, and nothing to press, once onboarding is done", () => {
    onDatabase("a")
    rememberDashboard()
    pendingStartup()
    renderApp()

    const frame = screen.getByRole("status", STARTING)
    expect(frame.getAttribute("aria-busy")).toBe("true")
    expect(
      within(frame).getByRole("heading", { name: "SurfSense" })
    ).toBeTruthy()
    expect(within(frame).getByRole("heading", { name: "Studio" })).toBeTruthy()
    expect(within(frame).queryAllByRole("button")).toEqual([])
    expect(within(frame).queryByRole("textbox")).toBeNull()
  })

  it("puts the composer where the dashboard will: centred on a new chat", () => {
    onDatabase("a")
    rememberDashboard()
    pendingStartup()
    renderApp()

    const frame = screen.getByRole("status", STARTING)
    expect(frame.querySelector("[data-composer-outline=center]")).toBeTruthy()
    expect(frame.querySelector("[data-composer-outline=bottom]")).toBeNull()
  })

  it("puts the composer where the dashboard will: at the bottom of an open thread", () => {
    onDatabase("a")
    rememberDashboard()
    localStorage.setItem("surfsense:last-workspace:v1", "1")
    localStorage.setItem("surfsense:last-thread:1:v1", "10")
    pendingStartup()
    renderApp()

    const frame = screen.getByRole("status", STARTING)
    expect(frame.querySelector("[data-composer-outline=bottom]")).toBeTruthy()
    expect(frame.querySelector("[data-composer-outline=center]")).toBeNull()
  })
})

describe("startup's memory of onboarding", () => {
  it("is kept once the API says onboarding is done", async () => {
    onDatabase("a")
    completedInstall()
    renderApp()

    await screen.findByRole(
      "navigation",
      { name: "Workspaces" },
      { timeout: 10_000 }
    )
    expect(expectsDashboard()).toBe(true)
  }, 15_000)

  it("is dropped once the API says onboarding is needed again", async () => {
    onDatabase("a")
    rememberDashboard()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input) === "/llm/onboarding"
          ? Response.json({ completed: false })
          : Response.json({ detail: "not found" }, { status: 404 })
      )
    )
    renderApp()

    await screen.findByRole("button", { name: "Start setting up" })
    expect(expectsDashboard()).toBe(false)
  })
})

describe("startup's reveal", () => {
  async function workspaceRail() {
    return screen.findByRole(
      "navigation",
      { name: "Workspaces" },
      { timeout: 10_000 }
    )
  }

  it("fades the dashboard's contents into the frame after a wait long enough to see", async () => {
    onDatabase("a")
    rememberDashboard()
    completedInstall({ onboardingAfterMs: 250 })
    renderApp()

    expect((await workspaceRail()).className).toContain("ss-reveal")
  }, 15_000)

  it("draws them at once after a wait too short to see", async () => {
    onDatabase("a")
    rememberDashboard()
    completedInstall()
    renderApp()

    expect((await workspaceRail()).className).not.toContain("ss-reveal")
  }, 15_000)

  it("never fades without a frame to fade into", async () => {
    onDatabase("a")
    completedInstall({ onboardingAfterMs: 250 })
    renderApp()

    expect((await workspaceRail()).className).not.toContain("ss-reveal")
  }, 15_000)
})
