import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { ChatModes, MeasuredRow, ModelCapability } from "./api"
import { ModelCapabilitySummary } from "./model-capability"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

const UNTESTED: ChatModes = {
  agentic_allowed: true,
  blocked: null,
  default_mode: "basic",
  reason: { code: "untested", values: {} },
  remembered_mode: null,
}

const MEASURED: MeasuredRow = {
  key: "claude-haiku-4-5",
  suite: "create-and-edit",
  assumed: false,
  suite_version: 1,
  measured_on: "2026-10-04",
  provider: "anthropic",
  host: "api.anthropic.com",
  reads_images: true,
  passed: 5,
  counted: 8,
  provisional: false,
}

function capability(overrides: Partial<ModelCapability> = {}): ModelCapability {
  return {
    level: "not_measured",
    label_key: "not_measured",
    reason: { code: "no_row", values: {} },
    note: null,
    measured: null,
    modes: UNTESTED,
    studio: "full",
    ...overrides,
  }
}

function serving(capabilityRead: ModelCapability | null) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/selection/text_gen" && !init?.method) {
      return Response.json({
        model_type: "text_gen",
        provider: "openai_compatible",
        connection_id: 1,
        name: "gpt-4o-mini",
        updated_at: "2026-10-04T00:00:00Z",
        capability: capabilityRead,
      })
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

/** Opens the disclosure and returns what it shows. */
async function opened(read: ModelCapability): Promise<string> {
  vi.stubGlobal("fetch", serving(read))
  const user = userEvent.setup()
  render(<ModelCapabilitySummary />)
  await user.click(
    await screen.findByRole("button", { name: "What this model can do" })
  )
  return (
    screen.getByRole("region", { name: "What this model can do" })
      .textContent ?? ""
  )
}

describe("what the chat model in use can do", () => {
  it("is offered in a production build too, closed until asked", async () => {
    vi.stubEnv("DEV", false)
    vi.stubGlobal("fetch", serving(capability()))

    render(<ModelCapabilitySummary />)

    const toggle = await screen.findByRole("button", {
      name: "What this model can do",
    })
    expect(toggle.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("region")).toBeNull()
  })

  it("says nothing while no chat model is chosen", async () => {
    const fetch = serving(null)
    vi.stubGlobal("fetch", fetch)

    const { container } = render(<ModelCapabilitySummary />)

    await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
    // Let the selection read settle, so an empty box is not just a slow one.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(container.textContent).toBe("")
  })

  it("says what a model at the bar does in chat and in Studio, and how it was tested", async () => {
    const shown = await opened(
      capability({
        level: "agent",
        label_key: "agent",
        reason: { code: "measured_pass", values: {} },
        measured: { ...MEASURED, passed: 8 },
        modes: { ...UNTESTED, default_mode: "agentic" },
      })
    )

    expect(shown).toContain(
      "Basic and Agentic. Choose the mode in the composer."
    )
    expect(shown).toContain(
      "Full designed pages, and Word, Excel and slide files."
    )
    expect(shown).toContain("Tested: 8 of 8 cases passed, Oct 4, 2026.")
  })

  it("says a model near the bar may need a nudge in Agentic", async () => {
    const shown = await opened(
      capability({
        level: "agent_limited",
        label_key: "agent_limited",
        measured: MEASURED,
      })
    )

    expect(shown).toContain(
      "Basic and Agentic. In Agentic it may need a nudge, such as asking it to check its work."
    )
  })

  it("says a model below the bar makes simple Studio files, and what a stronger one adds", async () => {
    const shown = await opened(
      capability({
        level: "studio_only",
        label_key: "studio_only",
        measured: { ...MEASURED, passed: 1, counted: 2, provisional: true },
        studio: "simple",
      })
    )

    expect(shown).toContain(
      "Basic and Agentic. Agentic may not finish longer tasks well."
    )
    expect(shown).toContain(
      "Simple pages and documents. A stronger model writes full designed pages and Word, Excel and slide files."
    )
    expect(shown).toContain(
      "From a short test: 1 of 2 cases passed, Oct 4, 2026."
    )
  })

  it.each([
    [
      "tool_calls_unsupported",
      "Basic only. Agentic needs a model that can use tools.",
    ],
    [
      "window_below_floor",
      "Basic only. Agentic needs a context window of at least 32,768 tokens.",
    ],
    [
      "agent_not_installed",
      "Basic only. This install doesn’t include the agent.",
    ],
  ])("says why %s keeps chat to Basic", async (blocked, line) => {
    const shown = await opened(
      capability({
        modes: { ...UNTESTED, agentic_allowed: false, blocked },
      })
    )

    expect(shown).toContain(line)
  })

  it.each([
    [
      "an untested model",
      capability(),
      "Basic and Agentic. Agentic isn’t tested with this model yet.",
      "Not tested yet.",
    ],
    [
      "a flagship assumed to pass",
      capability({
        level: "agent",
        label_key: "agent",
        reason: { code: "assumed", values: {} },
        measured: { ...MEASURED, suite: "assumed", assumed: true },
      }),
      "Basic and Agentic. Choose the mode in the composer.",
      "Not tested. Expected to pass, as a flagship model.",
    ],
    [
      "a model measured through a provider's host",
      capability({
        reason: { code: "measured_elsewhere", values: { host: "openrouter.ai" } },
      }),
      "Basic and Agentic. Agentic isn’t tested with this model yet.",
      "Tested through openrouter.ai, not on your own computer or server.",
    ],
    [
      "a name that moves",
      capability({ reason: { code: "alias", values: {} } }),
      "Basic and Agentic. Agentic isn’t tested with this model yet.",
      "Not tested. A name ending in “latest” can point to a new model.",
    ],
  ])("says how %s was tested", async (_case, read, chat, tested) => {
    const shown = await opened(read)

    expect(shown).toContain(chat)
    expect(shown).toContain(tested)
    expect(shown).not.toContain("cases passed")
  })
})
