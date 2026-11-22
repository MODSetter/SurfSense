import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { useRefreshModels } from "../../models-query"
import { useConnectionModels } from "../models/use-connection-models"
import type { Connection } from "./api"
import { useConnections, useDeleteConnection } from "./use-connections"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const CLAUDE: Connection = {
  id: 3,
  label: "Claude plan",
  provider: "openai_compatible",
  base_url: "https://api.anthropic.com",
  catalog_provider: "anthropic",
  has_api_key: false,
  auth_kind: "claude_plan",
  signed_in: false,
  account_email: null,
  serves: ["text_gen"],
  created_at: "2026-10-17T00:00:00",
  updated_at: "2026-10-17T00:00:00",
}

function Card({ connection }: { connection: Connection }) {
  const remove = useDeleteConnection()
  const models = useConnectionModels(connection, true)
  return (
    <section aria-label={connection.label}>
      {models.isError ? <p>{models.error.message}</p> : null}
      <p>{models.data?.map((model) => model.name).join(", ")}</p>
      <button type="button" onClick={() => remove.mutate(connection.id)}>
        Delete
      </button>
    </section>
  )
}

function Settings() {
  const connections = useConnections()
  // What the app does once a connection is made.
  const refresh = useRefreshModels()
  return (
    <>
      {connections.data?.map((connection) => (
        <Card key={connection.id} connection={connection} />
      ))}
      <button type="button" onClick={() => void refresh()}>
        Connected
      </button>
    </>
  )
}

describe("deleting a connection", () => {
  it("never asks the server about it again, so its card never says it is gone", async () => {
    let deleted = false
    const asked: string[] = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        asked.push(`${init?.method ?? "GET"} ${path}`)
        if (init?.method === "DELETE") {
          deleted = true
          return new Response(null, { status: 204 })
        }
        if (path === "/llm/connections")
          return Response.json(deleted ? [] : [CLAUDE])
        if (path === "/llm/connections/3/models")
          return deleted
            ? Response.json({ detail: "connection not found" }, { status: 404 })
            : Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()
    render(<Settings />)

    await user.click(await screen.findByRole("button", { name: "Delete" }))
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Claude plan" })).toBeNull()
    )

    const afterDelete = asked.slice(asked.indexOf("DELETE /llm/connections/3"))
    expect(afterDelete).not.toContain("GET /llm/connections/3/models")
  })
})

describe("a new connection given a deleted one's id", () => {
  it("shows its own models, never the deleted one's", async () => {
    // SQLite gives the highest id out again once it is deleted.
    const again = { ...CLAUDE, created_at: "2026-10-17T00:05:00" }
    let deleted = false
    let added = false
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (init?.method === "DELETE") {
          deleted = true
          return new Response(null, { status: 204 })
        }
        if (path === "/llm/connections")
          return Response.json(added ? [again] : deleted ? [] : [CLAUDE])
        if (path === "/llm/connections/3/models")
          return Response.json([{ name: added ? "new-model" : "old-model" }])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()
    render(<Settings />)
    expect(await screen.findByText("old-model")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete" }))
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Claude plan" })).toBeNull()
    )

    added = true
    await user.click(screen.getByRole("button", { name: "Connected" }))

    expect(await screen.findByText("new-model")).toBeTruthy()
    expect(screen.queryByText("old-model")).toBeNull()
  })
})
