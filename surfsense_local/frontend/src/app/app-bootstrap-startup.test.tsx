import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { writeNextNewChatMode } from "@/features/chat/modes/next-new-chat-mode-store"
import {
  expectsDashboard,
  rememberDashboard,
} from "@/features/startup/dashboard-hint"
import { readStartupLayout } from "@/features/startup/startup-layout"
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
function completedInstall({
  onboardingAfterMs = 0,
  selection = null as Record<string, unknown> | null,
  // Holds the first answer until the test resolves it.
  gate = null as Promise<void> | null,
} = {}) {
  const requested: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      requested.push(path)
      if (path === "/llm/onboarding") {
        await new Promise((resolve) => setTimeout(resolve, onboardingAfterMs))
        await gate
        return Response.json({ completed: true })
      }
      if (path === "/plugins/third-party") {
        return Response.json({ allowed: true })
      }
      if (path === "/llm/selection/text_gen" && selection) {
        return Response.json(selection)
      }
      if (path === "/llm/connections/1/models" && selection) {
        return Response.json([
          {
            connection_id: 1,
            connection_label: "Remote",
            name: selection.name,
            types: ["text_gen"],
            capability_source: "catalog",
            selectable_for: ["text_gen"],
          },
        ])
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
        path === "/plugins" ||
        path === "/workspaces/1/chat/threads" ||
        path === "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
      ) {
        return Response.json([])
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return requested
}

function gated() {
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  return { gate, release }
}

// The loading screen, labelled for assistive tech while it is busy.
function startupScreen() {
  return screen.getByRole("main", STARTING)
}

function frameBox() {
  return within(startupScreen()).getByRole<HTMLTextAreaElement>("textbox", {
    name: "Message",
  })
}

async function dashboardRail() {
  return screen.findByRole(
    "navigation",
    { name: "Workspaces" },
    { timeout: 10_000 }
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
  it("says the app is starting, for assistive tech", () => {
    pendingStartup()
    renderApp()

    expect(startupScreen().getAttribute("aria-busy")).toBe("true")
    expect(screen.getByRole("status").textContent).toBe("Starting SurfSense")
  })

  it("is blank until onboarding has been seen done on this database", () => {
    onDatabase("a")
    pendingStartup()
    renderApp()

    expect(within(startupScreen()).queryByRole("heading")).toBeNull()
    expect(within(startupScreen()).queryByRole("textbox")).toBeNull()
  })

  it("is blank without the desktop, whose data can change under the browser", () => {
    rememberDashboard()
    pendingStartup()
    renderApp()

    expect(within(startupScreen()).queryByRole("heading")).toBeNull()
  })

  it("draws the dashboard's constant parts, and nothing to press, once onboarding is done", () => {
    onDatabase("a")
    rememberDashboard()
    pendingStartup()
    renderApp()

    const frame = startupScreen()
    expect(
      within(frame).getByRole("heading", { name: "SurfSense" })
    ).toBeTruthy()
    expect(within(frame).getByRole("heading", { name: "Studio" })).toBeTruthy()
    expect(within(frame).queryAllByRole("button")).toEqual([])
  })

  it("holds an open thread's place with its messages' skeleton, and no composer until it loads", () => {
    onDatabase("a")
    rememberDashboard()
    localStorage.setItem("surfsense:last-workspace:v1", "1")
    localStorage.setItem("surfsense:last-thread:1:v1", "10")
    pendingStartup()
    renderApp()

    const frame = startupScreen()
    expect(frame.querySelector("[data-slot=skeleton]")).toBeTruthy()
    expect(within(frame).queryByRole("textbox")).toBeNull()
  })
})

describe("typing while the app loads", () => {
  function onNewChat() {
    onDatabase("a")
    rememberDashboard()
  }

  it("takes typing in a new chat's box, focused from the start", async () => {
    onNewChat()
    pendingStartup()
    renderApp()

    expect(document.activeElement).toBe(frameBox())
    await userEvent.type(frameBox(), "find jobs")
    expect(frameBox().value).toBe("find jobs")
  })

  it("sends nothing and adds no line on Enter, with nowhere to send yet", async () => {
    onNewChat()
    pendingStartup()
    renderApp()

    await userEvent.type(frameBox(), "find jobs{Enter}")
    expect(frameBox().value).toBe("find jobs")
  })

  it("carries what was typed into the dashboard's composer", async () => {
    onNewChat()
    const { gate, release } = gated()
    completedInstall({ gate })
    renderApp()

    await userEvent.type(frameBox(), "find jobs")
    release()
    await dashboardRail()
    await waitFor(() =>
      expect(
        screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
          .value
      ).toBe("find jobs")
    )
  }, 15_000)

  it("shows the plugin list loading on `@` when new chats open in Agentic", async () => {
    onNewChat()
    writeNextNewChatMode("agentic")
    pendingStartup()
    renderApp()

    await userEvent.type(frameBox(), "find jobs with @ind")
    // A busy group: nothing to pick until the plugins arrive.
    const list = within(startupScreen()).getByRole("group", {
      name: "Plugins",
    })
    expect(list.getAttribute("aria-busy")).toBe("true")
    expect(list.querySelector("[data-slot=skeleton]")).toBeTruthy()
  })

  it("shows no plugin list on `@` when new chats open in Q&A", async () => {
    onNewChat()
    writeNextNewChatMode("basic")
    pendingStartup()
    renderApp()

    await userEvent.type(frameBox(), "find jobs with @ind")
    expect(
      within(startupScreen()).queryByRole("group", { name: "Plugins" })
    ).toBeNull()
  })

  it("closes the plugin list once the caret leaves the mention", async () => {
    onNewChat()
    writeNextNewChatMode("agentic")
    pendingStartup()
    renderApp()

    await userEvent.type(frameBox(), "ask @goo about it")
    expect(
      within(startupScreen()).queryByRole("group", { name: "Plugins" })
    ).toBeNull()
  })

  it("waits for a composition in progress before the dashboard takes the box", async () => {
    onNewChat()
    const { gate, release } = gated()
    completedInstall({ gate })
    renderApp()

    fireEvent.compositionStart(frameBox())
    release()
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(startupScreen().getAttribute("aria-busy")).toBe("true")
    fireEvent.compositionEnd(frameBox())
    await dashboardRail()
  }, 15_000)

  it("starts loading the plugins before the dashboard asks for them", async () => {
    onNewChat()
    const requested = completedInstall()
    renderApp()

    await dashboardRail()
    await waitFor(() =>
      expect(requested).toContain("/workspaces/1/chat/threads")
    )
    expect(requested.indexOf("/plugins")).toBeGreaterThan(-1)
    expect(requested.indexOf("/plugins")).toBeLessThan(
      requested.indexOf("/workspaces/1/chat/threads")
    )
  }, 15_000)

  it("keeps the dashboard composer's text solid while its controls fade in", async () => {
    onNewChat()
    completedInstall({ onboardingAfterMs: 250 })
    renderApp()

    await dashboardRail()
    expect(
      screen
        .getByRole("textbox", { name: "Message" })
        .hasAttribute("data-reveal-steady")
    ).toBe(true)
  }, 15_000)
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

  it("keeps the mode the next new chat opens in, for the frame's mentions", async () => {
    onDatabase("a")
    completedInstall({
      selection: {
        model_type: "text_gen",
        provider: "openai_compatible",
        connection_id: 1,
        name: "anthropic/claude-fable-5",
        updated_at: "2026-11-01T00:00:00Z",
        capability: {
          modes: {
            agentic_allowed: true,
            blocked: null,
            default_mode: "agentic",
            reason: { code: "assumed", values: {} },
          },
        },
      },
    })
    renderApp()

    await screen.findByRole(
      "navigation",
      { name: "Workspaces" },
      { timeout: 10_000 }
    )
    expect(readStartupLayout().mentions).toBe(true)
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
