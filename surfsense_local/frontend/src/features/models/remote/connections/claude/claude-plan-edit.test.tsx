import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Connection } from "../api"
import { ConnectionForm } from "../connection-form"

const PLAN: Connection = {
  id: 7,
  label: "Claude plan",
  provider: "openai_compatible",
  base_url: "https://api.anthropic.com",
  catalog_provider: "anthropic",
  has_api_key: false,
  auth_kind: "claude_plan",
  signed_in: false,
  account_email: null,
  serves: ["text_gen"],
  created_at: "2026-10-16T00:00:00",
  updated_at: "2026-10-16T00:00:00",
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("editing a Claude plan connection", () => {
  it("asks for no URL or key, and only renames it", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/llm/connections/7" && init?.method === "PUT")
          return Response.json({ ...PLAN, label: "Work Claude" })
        return Response.json([])
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const onSaved = vi.fn()
    const user = userEvent.setup()
    render(
      <ConnectionForm connection={PLAN} onCancel={vi.fn()} onSaved={onSaved} />
    )

    expect(screen.queryByLabelText("Base URL")).toBeNull()
    expect(screen.queryByLabelText("API key")).toBeNull()
    expect(screen.getByText(/run claude in a terminal/)).toBeTruthy()
    const save = screen.getByRole("button", { name: "Save changes" })
    expect(save.hasAttribute("disabled")).toBe(true)

    const name = screen.getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Work Claude")
    await user.click(save)

    await waitFor(() =>
      expect(onSaved).toHaveBeenCalledWith({ ...PLAN, label: "Work Claude" })
    )
    const sent = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")
    expect(JSON.parse(String(sent?.[1]?.body))).toMatchObject({
      label: "Work Claude",
      base_url: "https://api.anthropic.com",
    })
  })
})
