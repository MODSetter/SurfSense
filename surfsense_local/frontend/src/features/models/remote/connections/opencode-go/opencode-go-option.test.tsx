import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Connection } from "../api"
import { OpencodeGoOption } from "./opencode-go-option"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const GO_URL = "https://opencode.ai/inference/go/openai/v1"

const goProvider = (fields: Record<string, unknown> = {}) => ({
  id: "opencode-go",
  name: "OpenCode Go",
  doc: null,
  connect: {
    status: "ready",
    base_url: GO_URL,
    base_url_origin: "models.dev",
    account_fields: [],
    key: "required",
    local: false,
    reason: null,
    ...fields,
  },
  type_counts: { text_gen: 12 },
  connections: 0,
})

const CONNECTED: Connection = {
  id: 9,
  label: "Team Go",
  provider: "openai_compatible",
  base_url: GO_URL,
  catalog_provider: "opencode-go",
  has_api_key: true,
  auth_kind: "api_key",
  signed_in: false,
  account_email: null,
  serves: ["text_gen"],
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
}

/** The backend's routes: the provider list, the saved connections, and a save. */
function serve({
  providers = [goProvider()],
  connections = [],
}: { providers?: unknown[]; connections?: Connection[] } = {}) {
  const sent: { path: string; method: string; body: unknown }[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (path === "/llm/catalog/remote") return Response.json(providers)
      if (path === "/llm/connections" && method === "GET") {
        return Response.json(connections)
      }
      sent.push({ path, method, body: JSON.parse(String(init?.body)) })
      return Response.json(CONNECTED, { status: 201 })
    })
  )
  return sent
}

const row = () =>
  screen.queryByRole("region", { name: "Use your OpenCode Go plan" })

describe("connecting an OpenCode Go plan", () => {
  it("is offered for the slots Go has models for", async () => {
    serve()
    const { rerender } = render(
      <OpencodeGoOption modelType="text_gen" onConnected={vi.fn()} />
    )
    await waitFor(() => expect(row()).not.toBeNull())

    rerender(<OpencodeGoOption modelType="audio_gen" onConnected={vi.fn()} />)
    expect(row()).toBeNull()
  })

  it("is not offered when the catalog cannot reach Go", async () => {
    serve({ providers: [goProvider({ status: "unreachable" })] })
    render(<OpencodeGoOption modelType="text_gen" onConnected={vi.fn()} />)
    // Let the provider list settle before checking nothing came.
    await act(() => new Promise((settle) => setTimeout(settle, 0)))

    expect(row()).toBeNull()
  })

  it("saves a key as an OpenCode Go server and hands it over", async () => {
    const sent = serve()
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<OpencodeGoOption modelType="text_gen" onConnected={onConnected} />)

    await user.click(await screen.findByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog")
    expect(dialog.textContent).toContain("needs a Go subscription")
    await user.type(screen.getByLabelText("API key"), "oc_sk_go")
    await user.click(screen.getByRole("button", { name: "Save server" }))

    await waitFor(() =>
      expect(onConnected).toHaveBeenCalledWith(
        expect.objectContaining({ id: 9 })
      )
    )
    expect(sent).toEqual([
      {
        path: "/llm/connections",
        method: "POST",
        body: expect.objectContaining({
          label: "OpenCode Go",
          base_url: GO_URL,
          catalog_provider: "opencode-go",
          api_key: "oc_sk_go", // pragma: allowlist secret
        }),
      },
    ])
  })

  it("opens the models of a Go server added anywhere", async () => {
    serve({ connections: [CONNECTED] })
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<OpencodeGoOption modelType="text_gen" onConnected={onConnected} />)

    expect(await screen.findByText("Connected as Team Go")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Show models" }))

    expect(onConnected).toHaveBeenCalledWith(CONNECTED)
  })
})
