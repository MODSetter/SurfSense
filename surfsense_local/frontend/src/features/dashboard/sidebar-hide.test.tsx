import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { DashboardPage } from "./dashboard-page"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

function renderDashboard() {
  return render(
    <ThemeProvider>
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    </ThemeProvider>
  )
}

const column = () => document.getElementById("workspace-left-column")!

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  vi.stubGlobal("surfsense", { apiUrl: "", platform: "darwin" })
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/")) return Response.json([])
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("hiding the left sidebar", () => {
  it("hides from the title bar, gives the chat its room, and shows again", async () => {
    const user = userEvent.setup()
    renderDashboard()

    const hide = await screen.findByRole("button", { name: "Hide sidebar" })
    expect(hide.closest(".titlebar-controls")).toBeTruthy()
    expect(column().style.width).toBe("272px")

    await user.click(hide)
    expect(column().style.width).toBe("0px")
    expect(
      screen.queryByRole("separator", { name: "Resize sidebar" })
    ).toBeNull()

    await user.click(screen.getByRole("button", { name: "Show sidebar" }))
    expect(column().style.width).toBe("272px")
    expect(
      screen.getByRole("separator", { name: "Resize sidebar" })
    ).toBeTruthy()
  })

  it("stays hidden the next time the app opens", async () => {
    const user = userEvent.setup()
    const first = renderDashboard()
    await user.click(
      await screen.findByRole("button", { name: "Hide sidebar" })
    )
    first.unmount()

    renderDashboard()
    await screen.findByRole("button", { name: "Show sidebar" })
    expect(column().style.width).toBe("0px")
  })

  it("toggles with the keyboard shortcut", async () => {
    const user = userEvent.setup()
    renderDashboard()
    await screen.findByRole("button", { name: "Hide sidebar" })

    await user.keyboard("{Meta>}b{/Meta}")
    expect(column().style.width).toBe("0px")
    await user.keyboard("{Control>}b{/Control}")
    expect(column().style.width).toBe("272px")
  })

  describe("floating in at the left edge", () => {
    const newChat = () => within(column()).getByText("New chat")
    const isAvailable = () => newChat().closest("[inert]") === null
    const edge = () =>
      document.querySelector<HTMLElement>('[data-slot="sidebar-reveal-edge"]')!

    async function hiddenDashboard() {
      localStorage.setItem("surfsense:sidebar:v1", "collapsed")
      renderDashboard()
      await screen.findByRole("button", { name: "Show sidebar" })
    }

    it("offers nothing until the edge is hovered, and leaves the chat its room", async () => {
      const user = userEvent.setup()
      await hiddenDashboard()
      expect(isAvailable()).toBe(false)

      await user.hover(edge())
      await waitFor(() => expect(isAvailable()).toBe(true))
      expect(column().style.width).toBe("0px")
    })

    it("hides again once the pointer moves away", async () => {
      const user = userEvent.setup()
      await hiddenDashboard()
      await user.hover(edge())
      await waitFor(() => expect(isAvailable()).toBe(true))

      await user.hover(newChat())
      await user.hover(screen.getByRole("region", { name: "Conversation" }))
      await waitFor(() => expect(isAvailable()).toBe(false))
    })

    it("stays while a dialog it opened is up", async () => {
      const user = userEvent.setup()
      await hiddenDashboard()
      await user.hover(edge())
      await waitFor(() => expect(isAvailable()).toBe(true))

      await user.click(screen.getByRole("button", { name: "Chats" }))
      await screen.findByRole("dialog")
      fireEvent.pointerMove(document.body)
      await act(() => new Promise((settled) => window.setTimeout(settled, 500)))
      expect(isAvailable()).toBe(true)
    })

    it("opens for files dragged to the edge", async () => {
      await hiddenDashboard()
      fireEvent.dragEnter(edge())
      await waitFor(() => expect(isAvailable()).toBe(true))
    })

    it("has no edge while the sidebar is showing", async () => {
      renderDashboard()
      await screen.findByRole("button", { name: "Hide sidebar" })
      expect(edge()).toBeNull()
    })
  })

  describe("in the Docker image", { tags: ["docker"] }, () => {
    it("keeps one toggle in the columns' corner, shown or hidden", async () => {
      const user = userEvent.setup()
      renderDashboard()

      const hide = await screen.findByRole("button", { name: "Hide sidebar" })
      expect(hide.closest(".titlebar-controls")).toBeNull()
      // Pinned outside the sidebar, so it stays put while the column slides.
      expect(
        within(
          screen.getByRole("heading", { name: "SurfSense" }).closest("aside")!
        ).queryAllByRole("button", { name: "Hide sidebar" })
      ).toHaveLength(0)

      await user.click(hide)
      expect(hide.isConnected).toBe(true)
      expect(hide.getAttribute("aria-label")).toBe("Show sidebar")
      expect(
        within(
          screen.getByRole("region", { name: "Conversation" })
        ).queryAllByRole("button", { name: "Show sidebar" })
      ).toHaveLength(0)
    })
  })
})
