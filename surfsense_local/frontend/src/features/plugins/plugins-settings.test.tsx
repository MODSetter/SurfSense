import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Plugin } from "./api"
import { PluginsSettings } from "./plugins-settings"

function notes(extra: Partial<Plugin> = {}): Plugin {
  return {
    id: "notes",
    name: "Notes",
    source: "custom",
    publisher: "custom",
    url: "https://notes.example/mcp",
    hosts: ["notes.example"],
    enabled: true,
    connected_at: "2026-10-01T00:00:00Z",
    tools: [
      {
        name: "search",
        title: "Search notes",
        description: "Search the notes.",
        annotations: { readOnlyHint: true },
        enabled: true,
        approval: "ask",
      },
      {
        name: "count",
        title: null,
        description: "Count the words in a text.",
        annotations: {},
        enabled: true,
        approval: "ask",
      },
    ],
    ...extra,
  }
}

type Call = { method: string; path: string; body: unknown }

/** The plugin routes as the screen reaches them; `refuse` answers the next add instead. */
function api({
  plugins = [notes()],
  allowed = false,
  refuse,
}: {
  plugins?: Plugin[]
  allowed?: boolean
  refuse?: { status: number; code: string; message: string; name?: string }
} = {}): Call[] {
  const calls: Call[] = []
  let connected = plugins
  let thirdParty = allowed
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://api.test")
      const method = (init?.method ?? "GET").toUpperCase()
      const body = init?.body ? JSON.parse(String(init.body)) : null
      calls.push({ method, path: url.pathname, body })
      const [, , id, , tool] = url.pathname.split("/")
      if (url.pathname === "/plugins/third-party") {
        if (method === "PUT") thirdParty = body.allowed
        return method === "PUT"
          ? new Response(null, { status: 204 })
          : Response.json({ allowed: thirdParty })
      }
      if (url.pathname === "/plugins/custom") {
        if (refuse) {
          const { status, ...detail } = refuse
          return Response.json({ detail }, { status })
        }
        const added = notes({ name: body.name, url: body.url })
        connected = [...connected, added]
        return Response.json(added, { status: 201 })
      }
      if (method === "GET") return Response.json(connected)
      if (method === "DELETE") {
        connected = connected.filter((plugin) => plugin.id !== id)
        return new Response(null, { status: 204 })
      }
      connected = connected.map((plugin) =>
        plugin.id !== id
          ? plugin
          : tool
            ? {
                ...plugin,
                tools: plugin.tools.map((row) =>
                  row.name === tool ? { ...row, ...body } : row
                ),
              }
            : { ...plugin, ...body }
      )
      return Response.json(connected.find((plugin) => plugin.id === id))
    })
  )
  return calls
}

const changes = (calls: Call[]) => calls.filter((call) => call.method !== "GET")

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("plugins settings", () => {
  it("lists each plugin's tools, the read-only ones apart", async () => {
    api({ allowed: true })
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    const readOnly = within(plugin).getByRole("group", { name: "Read-only" })
    const others = within(plugin).getByRole("group", {
      name: "Can make changes",
    })
    expect(within(readOnly).getByText("Search notes")).toBeTruthy()
    expect(within(others).getByText("count")).toBeTruthy()
    expect(screen.getByText(/Plugins work in Agentic threads/)).toBeTruthy()
  })

  it("adds a server by its URL, with a key", async () => {
    const calls = api({ plugins: [], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(await screen.findByRole("button", { name: "Add MCP server" }))
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Notes")
    await user.type(
      within(dialog).getByLabelText("Server URL"),
      "https://notes.example/mcp"
    )
    await user.type(within(dialog).getByLabelText("Key"), "k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await screen.findByRole("region", { name: "Notes" })).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "POST",
        path: "/plugins/custom",
        body: { url: "https://notes.example/mcp", name: "Notes", token: "k-1" },
      },
    ])
  })

  it("says why a server was refused, in the app's words", async () => {
    api({
      plugins: [],
      refuse: {
        status: 422,
        code: "plugin_needs_sign_in",
        message:
          "This server needs a key or a sign-in before it lists its tools.",
      },
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(await screen.findByRole("button", { name: "Add MCP server" }))
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Notes")
    await user.type(
      within(dialog).getByLabelText("Server URL"),
      "https://notes.example/mcp"
    )
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "This server needs a key. Add one and try again."
    )
  })

  it("switches a tool off, and lets only a read-only one skip asking", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    await user.click(within(plugin).getByRole("switch", { name: "Use count" }))
    await user.click(
      within(plugin).getByRole("radio", { name: "Always allow Search notes" })
    )

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: "/plugins/notes/tools/count",
          body: { enabled: false },
        },
        {
          method: "PUT",
          path: "/plugins/notes/tools/search",
          body: { approval: "always" },
        },
      ])
    )
    expect(
      within(plugin).queryByRole("radio", { name: "Always allow count" })
    ).toBeNull()
    expect(within(plugin).getByText("Always asks")).toBeTruthy()
  })

  it("pauses a plugin without disconnecting it", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    await user.click(within(plugin).getByRole("switch", { name: "Use Notes" }))

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        { method: "PUT", path: "/plugins/notes", body: { enabled: false } },
      ])
    )
  })

  it("disconnects only once the user confirms", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    await user.click(
      within(plugin).getByRole("button", { name: "Disconnect Notes" })
    )
    const confirm = await screen.findByRole("alertdialog")
    expect(changes(calls)).toEqual([])
    await user.click(
      within(confirm).getByRole("button", { name: "Disconnect" })
    )

    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Notes" })).toBeNull()
    )
    expect(changes(calls)).toEqual([
      { method: "DELETE", path: "/plugins/notes", body: null },
    ])
  })

  it("keeps third-party plugins off until the user allows them", async () => {
    const calls = api()
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    expect(
      within(plugin).getByText("Not used until third-party plugins are allowed")
    ).toBeTruthy()
    await user.click(
      screen.getByRole("switch", { name: "Allow third-party plugins" })
    )
    const consent = await screen.findByRole("alertdialog")
    expect(changes(calls)).toEqual([])
    await user.click(within(consent).getByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: "/plugins/third-party",
          body: { allowed: true },
        },
      ])
    )
    await waitFor(() =>
      expect(
        within(plugin).queryByText(
          "Not used until third-party plugins are allowed"
        )
      ).toBeNull()
    )
  })
})
