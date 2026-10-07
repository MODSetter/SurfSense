import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import type { ChatModes, ModelCapability } from "./api"
import { ModelCapabilitySummary } from "./model-capability"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const UNTESTED: ChatModes = {
  agentic_allowed: true,
  blocked: null,
  default_mode: "basic",
  reason: { code: "untested", values: {} },
  remembered_mode: null,
}

function capability(overrides: Partial<ModelCapability> = {}): ModelCapability {
  return {
    level: "not_measured",
    label_key: "not_measured",
    reason: { code: "no_row", values: {} },
    note: null,
    measured: null,
    modes: UNTESTED,
    ...overrides,
  }
}

function serving(capabilityRead: ModelCapability) {
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

describe("the selected chat model's capability", () => {
  it("names a measured level, the evidence behind it, and the mode new chats start in", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          level: "agent_limited",
          label_key: "agent_limited",
          reason: {
            code: "measured_near",
            values: {
              passed: 5,
              counted: 8,
              suite_version: 1,
              measured_on: "2026-10-04",
            },
          },
          note: "Passed 5 of 8; ask it to check each page.",
          measured: {
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
            provisional: true,
          },
          modes: {
            ...UNTESTED,
            default_mode: "agentic",
            reason: {
              code: "measured_near",
              values: { passed: 5, counted: 8 },
            },
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText("Agentic, may need nudges")).toBeTruthy()
    expect(screen.getByText(/Passed 5 of 8 cases/)).toBeTruthy()
    expect(
      screen.getByText("Passed 5 of 8; ask it to check each page.")
    ).toBeTruthy()
    expect(screen.getByText("New chats start in Agentic mode.")).toBeTruthy()
  })

  it("describes the modes in place of the old agent trial", async () => {
    vi.stubGlobal("fetch", serving(capability()))

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText("Not tested")).toBeTruthy()
    expect(
      screen.getByText("New chats start in Basic (Q&A) mode.")
    ).toBeTruthy()
    expect(
      screen.getByText(/Choose Basic \(Q&A\) or Agentic for each new chat/)
    ).toBeTruthy()
    expect(screen.queryByRole("switch")).toBeNull()
    expect(screen.queryByText("Try the agent")).toBeNull()
  })

  it("says a low score sets the default, not what the model may do", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          level: "studio_only",
          label_key: "studio_only",
          reason: { code: "measured_fail", values: {} },
          measured: {
            key: "gemma-4-31b-it",
            suite: "create-and-edit",
            assumed: false,
            suite_version: 1,
            measured_on: "2026-10-04",
            provider: "openrouter",
            host: "openrouter.ai",
            reads_images: true,
            passed: 2,
            counted: 8,
            provisional: true,
          },
          modes: {
            ...UNTESTED,
            reason: {
              code: "measured_below",
              values: { passed: 2, counted: 8 },
            },
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText("Low Agentic score")).toBeTruthy()
    expect(
      screen.getByText(/Choose Basic \(Q&A\) or Agentic for each new chat/)
    ).toBeTruthy()
  })

  it("says a flagship assumed to pass was not run, rather than 0 of 0", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          level: "agent",
          label_key: "agent",
          reason: { code: "assumed", values: {} },
          measured: {
            key: "claude-opus-4-6",
            suite: "assumed",
            assumed: true,
            suite_version: 1,
            measured_on: "2026-10-07",
            provider: "openrouter",
            host: "openrouter.ai",
            reads_images: true,
            passed: 0,
            counted: 0,
            provisional: true,
          },
          modes: {
            ...UNTESTED,
            default_mode: "agentic",
            reason: { code: "assumed", values: {} },
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText(/Not run: SurfSense expects/)).toBeTruthy()
    expect(screen.queryByText(/Passed 0 of 0/)).toBeNull()
  })

  it("says a pass measured on a provider's host does not hold on a server of one's own", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          reason: {
            code: "measured_elsewhere",
            values: { host: "openrouter.ai" },
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(
      await screen.findByText(
        "SurfSense measured this model through openrouter.ai, not on a computer of your own."
      )
    ).toBeTruthy()
  })

  it("says why a model that cannot use tools has no Agentic mode", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          modes: {
            ...UNTESTED,
            agentic_allowed: false,
            blocked: "tool_calls_unsupported",
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(
      await screen.findByText(
        "Agentic mode isn’t available: this model can’t use tools."
      )
    ).toBeTruthy()
  })
})
