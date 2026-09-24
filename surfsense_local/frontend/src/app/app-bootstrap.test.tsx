import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"
import { AppBootstrap } from "./app-bootstrap"

beforeEach(() => {
  // The onboarding welcome step mounts OnboardingDither, which reads matchMedia.
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
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("app bootstrap", () => {
  it("shows the filling logo while startup is pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {}))
    )

    render(
      <TooltipProvider>
        <AppBootstrap />
      </TooltipProvider>
    )

    // Named for assistive tech; the logo itself is decoration and says nothing.
    const loader = screen.getByRole("status", { name: "Starting SurfSense" })
    expect(loader.textContent).toBe("")
    expect(loader.querySelector(".ss-logo-fill-liquid")).toBeTruthy()
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
        if (path === "/llm/selection/text_gen") {
          return Response.json({ detail: "not found" }, { status: 404 })
        }
        if (path === "/llm/catalog/local") {
          return Response.json({
            rows: [],
            recommended_id: null,
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )

    render(<AppBootstrap />)

    expect(
      await screen.findByRole("heading", {
        name: "Air-gapped, open source NotebookLM alternative",
      })
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Start setting up" })
    ).toBeTruthy()
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
        if (path === "/llm/selection/text_gen") {
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

  // A completed install whose saved chat model is anthropic/claude-fable-5 on
  // connection 1, and whose check of that model answers `models`.
  function launchWithSavedModel(
    models: () => Response,
    other: (path: string, init?: RequestInit) => Response | null = () => null
  ) {
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
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        const answered = other(path, init)
        if (answered) return answered
        if (path === "/llm/onboarding") {
          return Response.json({ completed: true })
        }
        if (path === "/llm/selection/text_gen") {
          return Response.json({
            model_type: "text_gen",
            provider: "openai_compatible",
            connection_id: 1,
            name: "anthropic/claude-fable-5",
            updated_at: "2026-09-24T00:00:00Z",
          })
        }
        if (path === "/llm/connections/1/models") {
          return models()
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
          path === "/workspaces/1/chat/threads" ||
          path ===
            "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    render(
      <TooltipProvider>
        <AppBootstrap />
        <EgressPrompt />
      </TooltipProvider>
    )
  }

  it.each([
    {
      status: 409,
      code: "unreadable_secret",
      reason:
        "Couldn’t use anthropic/claude-fable-5, its saved key has to be entered again.",
    },
    {
      status: 502,
      code: "provider_unreachable",
      reason: "Couldn’t reach the server for anthropic/claude-fable-5.",
    },
  ])(
    "opens without the chosen model and says why when its check fails with $code",
    async ({ status, code, reason }) => {
      // A key saved under a lost keychain secret, or a remote endpoint that is
      // offline, must cost the user that model, not the whole app.
      launchWithSavedModel(() =>
        Response.json({ detail: { code, message: "failed" } }, { status })
      )

      expect(
        await screen.findByRole(
          "button",
          { name: "Set up model" },
          { timeout: 10_000 }
        )
      ).toBeTruthy()
      const notice = screen.getByRole("status")
      expect(notice.textContent).toContain(reason)
      expect(
        within(notice).getByRole("button", { name: "Open settings" })
      ).toBeTruthy()
      expect(screen.queryByText("SurfSense could not start")).toBeNull()
    },
    15_000
  )

  it("keeps the model when sending to its host is off, and asks before any send", async () => {
    // Egress off is a consent not yet given, not a broken model. The question is
    // put by the notice, when the user chooses to answer it, never by a send.
    let allowed = false
    launchWithSavedModel(
      () =>
        allowed
          ? Response.json([
              {
                connection_id: 1,
                connection_label: "OpenRouter",
                name: "anthropic/claude-fable-5",
                types: ["text_gen"],
                capability_source: "catalog",
                selectable_for: ["text_gen"],
              },
            ])
          : Response.json(
              {
                detail: {
                  code: "egress_disabled",
                  message:
                    "sending data to openrouter.ai is off in Settings > Network",
                  destination: "host:openrouter.ai",
                  host: "openrouter.ai",
                },
              },
              { status: 403 }
            ),
      (path, init) => {
        if (path === "/egress/host:openrouter.ai" && init?.method === "PUT") {
          allowed = true
          return Response.json({
            destination: "host:openrouter.ai",
            enabled: true,
          })
        }
        return null
      }
    )

    const reason = await screen.findByText(
      "Sending data to openrouter.ai is off.",
      {},
      { timeout: 10_000 }
    )
    const notice = reason.closest<HTMLElement>("[role=status]")!
    expect(screen.queryByRole("button", { name: "Set up model" })).toBeNull()
    const message = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "Message",
    })
    expect(message.disabled).toBe(true)
    expect(message.getAttribute("placeholder")).toBe(
      "Allow sending to openrouter.ai to chat"
    )

    await userEvent.click(
      within(notice).getByRole("button", { name: "Allow…" })
    )
    const consent = await screen.findByRole("alertdialog")
    await userEvent.click(
      within(consent).getByRole("button", { name: "Allow" })
    )

    await waitFor(() =>
      expect(
        screen.queryByText("Sending data to openrouter.ai is off.")
      ).toBeNull()
    )
    expect(message.disabled).toBe(false)
  }, 15_000)

  it("sends the user to Network, not the model list, when egress is off", async () => {
    launchWithSavedModel(() =>
      Response.json(
        {
          detail: {
            code: "egress_disabled",
            message:
              "sending data to openrouter.ai is off in Settings > Network",
            destination: "host:openrouter.ai",
            host: "openrouter.ai",
          },
        },
        { status: 403 }
      )
    )

    const reason = await screen.findByText(
      "Sending data to openrouter.ai is off.",
      {},
      { timeout: 10_000 }
    )
    await userEvent.click(
      within(reason.closest<HTMLElement>("[role=status]")!).getByRole(
        "button",
        { name: "Open settings" }
      )
    )
    const settings = await screen.findByRole("dialog")
    expect(
      within(settings).getByRole("heading", { name: "Network" })
    ).toBeTruthy()
  }, 15_000)
})
