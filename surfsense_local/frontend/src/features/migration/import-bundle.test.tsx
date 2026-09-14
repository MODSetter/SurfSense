import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { DashboardPage } from "@/features/dashboard/dashboard-page"
import { SettingsDialog } from "@/features/settings/settings-dialog"
import { render } from "@/test-utils"

const research = {
  id: 1,
  name: "Research",
  created_at: "2026-09-10T00:00:00Z",
  updated_at: "2026-09-10T00:00:00Z",
}
const empty = { ...research, id: 2, name: "Empty" }

function stubApi(importResponse: Response) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/migration/import" && init?.method === "POST") {
        return importResponse
      }
      if (path === "/workspaces") {
        return Response.json([research, empty])
      }
      if (path.startsWith("/workspaces/1/")) {
        return Response.json([])
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function renderEmptyDashboard() {
  return render(
    <ThemeProvider>
      <TooltipProvider>
        <DashboardPage
          selection={null}
          initialProviderAvailable={false}
          initialWorkspaces={[]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    </ThemeProvider>
  )
}

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
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  })
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("importing a SurfSense cloud export", () => {
  it("turns the bundle's workspaces into the user's workspaces", async () => {
    const fetchMock = stubApi(
      Response.json(
        {
          workspaces: [
            { id: 1, cloud_id: 12, name: "Research" },
            { id: 2, cloud_id: 13, name: "Empty" },
          ],
        },
        { status: 202 }
      )
    )
    const user = userEvent.setup()
    renderEmptyDashboard()

    const bundle = new File(["zip"], "surfsense-export.zip", {
      type: "application/zip",
    })
    await user.upload(
      screen.getByLabelText("Import from SurfSense cloud"),
      bundle
    )

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Research" })).toBeTruthy()
    })
    expect(screen.getByRole("button", { name: "Empty" })).toBeTruthy()
    const importCall = fetchMock.mock.calls.find(
      ([input]) => String(input) === "/migration/import"
    )
    const body = importCall?.[1]?.body
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get("file")).toBe(bundle)
  })

  it("shows the server's reason when the bundle is refused", async () => {
    stubApi(
      Response.json(
        { detail: "not a SurfSense export bundle: File is not a zip file" },
        { status: 422 }
      )
    )
    const user = userEvent.setup()
    renderEmptyDashboard()

    await user.upload(
      screen.getByLabelText("Import from SurfSense cloud"),
      new File(["nope"], "broken.zip", { type: "application/zip" })
    )

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toBe(
        "not a SurfSense export bundle: File is not a zip file"
      )
    })
    expect(screen.getByRole("heading", { name: "No workspaces" })).toBeTruthy()
  })

  it("is also offered in Settings, for a user who already has workspaces", async () => {
    const accepted = {
      workspaces: [{ id: 1, cloud_id: 12, name: "Research" }],
    }
    stubApi(Response.json(accepted, { status: 202 }))
    const onImported = vi.fn()
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <TooltipProvider>
          <SettingsDialog
            open
            section="general"
            onOpenChange={vi.fn()}
            onSectionChange={vi.fn()}
            onModelSelected={vi.fn()}
            onImported={onImported}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    expect(
      screen.getByRole("heading", { name: "Import from SurfSense cloud" })
    ).toBeTruthy()
    expect(
      screen.getByRole("button", {
        name: "More about importing from SurfSense cloud",
      })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Upload" })).toBeTruthy()
    const openExternal = vi.fn(async () => undefined)
    vi.stubGlobal("surfsense", {
      apiUrl: "",
      platform: "darwin",
      openDocument: vi.fn(async () => ""),
      revealDocument: vi.fn(async () => ""),
      openExternal,
    })
    const exportLink = screen.getByRole("link", { name: "SurfSense cloud" })
    expect(exportLink.getAttribute("href")).toBe("https://surfsense.com/sunset")
    await user.click(exportLink)
    expect(openExternal).toHaveBeenCalledWith("https://surfsense.com/sunset")

    await user.upload(
      screen.getByLabelText("Import from SurfSense cloud"),
      new File(["zip"], "surfsense-export.zip", { type: "application/zip" })
    )

    await waitFor(() => {
      expect(onImported).toHaveBeenCalledWith(accepted)
    })
  })
})
