import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { ModelCapability } from "./api"
import { ModelCapabilitySummary } from "./model-capability"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function capability(overrides: Partial<ModelCapability> = {}): ModelCapability {
  return {
    level: "not_measured",
    label_key: "not_measured",
    reason: { code: "no_row", values: {} },
    note: null,
    measured: null,
    agent_trial: { offered: true, enabled: false, blocked: null },
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
    if (path === "/llm/selection/text_gen/agent-trial") {
      const { enabled } = JSON.parse(String(init?.body))
      return Response.json(
        capability({ agent_trial: { offered: true, enabled, blocked: null } })
      )
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("the selected chat model's capability", () => {
  it("names a measured level and the evidence behind it", async () => {
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
            suite_version: 1,
            measured_on: "2026-10-04",
            provider: "anthropic",
            host: "api.anthropic.com",
            reads_images: true,
            passed: 5,
            counted: 8,
            provisional: true,
          },
          agent_trial: { offered: false, enabled: false, blocked: null },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText("Agent, may need nudges")).toBeTruthy()
    expect(screen.getByText(/Passed 5 of 8 cases/)).toBeTruthy()
    expect(
      screen.getByText("Passed 5 of 8; ask it to check each page.")
    ).toBeTruthy()
    expect(screen.queryByRole("switch")).toBeNull()
  })

  it("lets the user try the agent on a model nobody measured, with a warning", async () => {
    const fetchMock = serving(capability())
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelCapabilitySummary />)

    expect(await screen.findByText("Not measured")).toBeTruthy()
    expect(screen.getByText(/may stop early or make mistakes/)).toBeTruthy()
    await user.click(screen.getByRole("switch", { name: "Try the agent" }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/llm/selection/text_gen/agent-trial",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ enabled: true }),
        })
      )
    )
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

  it("says why a model that cannot carry the agent is not offered it", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        capability({
          agent_trial: {
            offered: false,
            enabled: false,
            blocked: "tool_calls_unconfirmed",
          },
        })
      )
    )

    render(<ModelCapabilitySummary />)

    expect(
      await screen.findByText(/does not say this model can call tools/)
    ).toBeTruthy()
    expect(screen.queryByRole("switch")).toBeNull()
  })
})
