import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { FirstPartyEntry, Plugin } from "./api"
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
    checked_at: "2026-10-01T00:00:00Z",
    check_failure: null,
    tools: [
      {
        name: "search",
        title: "Search notes",
        description: "Search the notes.",
        annotations: { readOnlyHint: true },
        enabled: true,
        approval: "ask",
        change: null,
      },
      {
        name: "count",
        title: null,
        description: "Count the words in a text.",
        annotations: {},
        enabled: true,
        approval: "ask",
        change: null,
      },
    ],
    ...extra,
  }
}

const SCRAPERS: FirstPartyEntry = {
  id: "scrapers",
  name: "SurfSense Scrapers",
  description: "Search Google and crawl sites.",
  author: "SurfSense",
  access: "license",
  hosts: ["plugins.surfsense.com"],
  connected: false,
}

type Call = { method: string; path: string; body: unknown }

/** The plugin routes as the screen reaches them; `refuse` answers an add or a new key instead. */
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
      if (url.pathname === "/plugins/first-party") {
        return Response.json(
          [SCRAPERS].map((entry) => ({
            ...entry,
            connected: connected.some((plugin) => plugin.id === entry.id),
          }))
        )
      }
      if (url.pathname === "/plugins/first-party/scrapers") {
        const added = notes({
          id: "scrapers",
          name: "SurfSense Scrapers",
          source: "first_party",
          publisher: "surfsense",
          hosts: ["plugins.surfsense.com"],
          check_failure: "needs_license",
          tools: [],
        })
        connected = [...connected, added]
        return Response.json(added, { status: 201 })
      }
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
      if (url.pathname.endsWith("/key")) {
        if (refuse) {
          const { status, ...detail } = refuse
          return Response.json({ detail }, { status })
        }
        connected = connected.map((plugin) =>
          plugin.id === id ? { ...plugin, check_failure: null } : plugin
        )
        return Response.json(connected.find((plugin) => plugin.id === id))
      }
      if (url.pathname.endsWith("/check")) {
        connected = connected.map((plugin) =>
          plugin.id === id ? { ...plugin, check_failure: null } : plugin
        )
        return Response.json(connected.find((plugin) => plugin.id === id))
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

    await user.click(
      await screen.findByRole("button", { name: "Add MCP server" })
    )
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

    await user.click(
      await screen.findByRole("button", { name: "Add MCP server" })
    )
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

  it("says a server could not be reached, and checks it again on request", async () => {
    const calls = api({
      plugins: [notes({ check_failure: "unreachable" })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    expect(within(plugin).getByText("Couldn’t connect")).toBeTruthy()
    await user.click(within(plugin).getByRole("button", { name: "Check now" }))

    expect(await within(plugin).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/notes/check", body: null },
    ])
  })

  it("asks for a new key when the server refused the last one, and saves it", async () => {
    const calls = api({
      plugins: [notes({ check_failure: "sign_in" })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    expect(within(plugin).getByText("Needs a new key")).toBeTruthy()
    await user.click(
      within(plugin).getByRole("button", { name: "Replace key" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("New key"), "k-2")
    await user.click(within(dialog).getByRole("button", { name: "Save" }))

    expect(await within(plugin).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "PUT", path: "/plugins/notes/key", body: { token: "k-2" } },
    ])
  })

  it("keeps the old key when the server refuses the new one", async () => {
    api({
      plugins: [notes({ check_failure: "sign_in" })],
      allowed: true,
      refuse: {
        status: 422,
        code: "plugin_needs_sign_in",
        message:
          "This server needs a key or a sign-in before it lists its tools.",
      },
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    await user.click(
      within(plugin).getByRole("button", { name: "Replace key" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("New key"), "wrong")
    await user.click(within(dialog).getByRole("button", { name: "Save" }))

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "The server refused this key. Check it and try again."
    )
  })

  it("marks the tools that are new or changed, which wait to be allowed", async () => {
    const base = notes()
    api({
      plugins: [
        notes({
          tools: [
            { ...base.tools[0], enabled: false, change: "changed" },
            { ...base.tools[1], enabled: false, change: "added" },
          ],
        }),
      ],
      allowed: true,
    })
    render(<PluginsSettings />)

    const plugin = await screen.findByRole("region", { name: "Notes" })
    expect(within(plugin).getByText("Changed")).toBeTruthy()
    expect(within(plugin).getByText("New")).toBeTruthy()
    expect(
      within(plugin).getByText(
        "Some tools are new or changed. They stay off until you allow them."
      )
    ).toBeTruthy()
  })

  it("lists SurfSense's plugins, which need a license, and connects one", async () => {
    const calls = api({ plugins: [], allowed: false })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    expect(within(surfsense).getByText("SurfSense Scrapers")).toBeTruthy()
    expect(within(surfsense).getByText("License required")).toBeTruthy()
    await user.click(within(surfsense).getByRole("button", { name: "Connect" }))

    expect(
      await screen.findByRole("region", { name: "SurfSense Scrapers" })
    ).toBeTruthy()
    expect(await within(surfsense).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/first-party/scrapers", body: null },
    ])
  })

  it("says why the license was refused, and opens Settings › License", async () => {
    api({
      plugins: [
        notes({ check_failure: "license_expired" }),
        notes({ id: "wiki", name: "Wiki", check_failure: "needs_license" }),
      ],
      allowed: true,
    })
    const onOpenLicense = vi.fn()
    const user = userEvent.setup()
    render(<PluginsSettings onOpenLicense={onOpenLicense} />)

    const expired = await screen.findByRole("region", { name: "Notes" })
    expect(within(expired).getByText("License expired")).toBeTruthy()
    const missing = screen.getByRole("region", { name: "Wiki" })
    expect(within(missing).getByText("Needs a license")).toBeTruthy()
    await user.click(
      within(missing).getByRole("button", { name: "License settings" })
    )

    expect(onOpenLicense).toHaveBeenCalledOnce()
  })
})
