import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { EgressPrompt } from "@/features/egress/egress-prompt"

import type { FirstPartyEntry, Plugin, RegistryEntry } from "./api"
import { PluginsSettings } from "./plugins-settings"

function notes(extra: Partial<Plugin> = {}): Plugin {
  return {
    id: "notes",
    name: "Notes",
    source: "custom",
    publisher: "custom",
    url: "https://notes.example/mcp",
    hosts: ["notes.example"],
    auth_type: "none",
    enabled: true,
    disconnected: false,
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
    removed_reason: null,
    ...extra,
  }
}

function listed(extra: Partial<RegistryEntry> = {}): RegistryEntry {
  return {
    id: "wiki",
    name: "Wiki",
    description: "Search the team wiki.",
    author: "Jane Doe",
    publisher: "community",
    verified: false,
    access: "free",
    access_note: null,
    auth_type: "none",
    auth_title: null,
    auth_description: null,
    hosts: ["wiki.example"],
    homepage: null,
    privacy_policy: "https://wiki.example/privacy",
    has_icon: false,
    connected: false,
    ...extra,
  }
}

const REGISTRY_FETCHED_AT = "2026-10-10T12:00:00Z"

const REDDIT: FirstPartyEntry = {
  id: "reddit",
  name: "Reddit",
  description: "Read Reddit posts, their comments and whole subreddits.",
  author: "SurfSense",
  access: "license",
  hosts: ["plugins.surfsense.com"],
  has_icon: true,
  connected: false,
}

type Call = { method: string; path: string; body: unknown }

const SIGN_IN_PAGE = "https://auth.example/authorize?state=8000.nonce"

/** The plugin routes as the screen reaches them; `refuse` answers an add or a new key instead. */
function api({
  plugins = [notes()],
  allowed = false,
  refuse,
  registry = [],
  registryHostAllowed = true,
  customSignsIn = false,
  signInEnds = "connected",
}: {
  plugins?: Plugin[]
  allowed?: boolean
  refuse?: { status: number; code: string; message: string; name?: string }
  registry?: RegistryEntry[]
  registryHostAllowed?: boolean
  /** Adding by URL reaches a server that asks for OAuth. */
  customSignsIn?: boolean
  /** What the second poll of a sign-in says; `waiting` never ends. */
  signInEnds?: "connected" | "failed" | "waiting"
} = {}): Call[] {
  const calls: Call[] = []
  let connected = plugins
  // The plugin a sign-in stores once it ends connected, and how often it was polled.
  let signingIn: Plugin | null = null
  let polls = 0
  const startSignIn = (plugin: Plugin) => {
    signingIn = plugin
    polls = 0
    return Response.json(
      {
        id: "s-1",
        plugin_id: plugin.id,
        authorization_url: SIGN_IN_PAGE,
      },
      { status: 202 }
    )
  }
  let thirdParty = allowed
  let hostAllowed = registryHostAllowed
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://api.test")
      const method = (init?.method ?? "GET").toUpperCase()
      const body = init?.body ? JSON.parse(String(init.body)) : null
      calls.push({ method, path: url.pathname, body })
      const [, , id, , tool] = url.pathname.split("/")
      if (url.pathname === "/egress/host:plugins.surfsense.com") {
        hostAllowed = true
        return Response.json({})
      }
      if (url.pathname === "/plugins/registry") {
        if (!thirdParty) {
          return Response.json({
            third_party_off: true,
            fetched_at: null,
            plugins: [],
            removed: [],
          })
        }
        if (!hostAllowed) {
          return Response.json(
            {
              detail: {
                code: "egress_disabled",
                message: "off",
                destination: "host:plugins.surfsense.com",
                host: "plugins.surfsense.com",
                hosts: ["plugins.surfsense.com"],
                purpose: "plugin_registry",
              },
            },
            { status: 403 }
          )
        }
        return Response.json({
          third_party_off: false,
          fetched_at: REGISTRY_FETCHED_AT,
          plugins: registry.map((entry) => ({
            ...entry,
            connected: connected.some((plugin) => plugin.id === entry.id),
          })),
          removed: [],
        })
      }
      if (url.pathname === "/plugins/sign-ins/s-1") {
        if (method === "DELETE") {
          signingIn = null
          return new Response(null, { status: 204 })
        }
        polls += 1
        const status = polls < 2 ? "waiting" : signInEnds
        if (status === "connected" && signingIn) {
          const signedIn: Plugin = signingIn
          connected = [
            ...connected.filter((plugin) => plugin.id !== signedIn.id),
            signedIn,
          ]
          signingIn = null
        }
        return Response.json({
          id: "s-1",
          plugin_id: "notes",
          status,
          message: status === "failed" ? "The sign-in was declined." : null,
        })
      }
      if (url.pathname === "/plugins/notes/sign-in") {
        return startSignIn({
          ...connected.find((plugin) => plugin.id === "notes")!,
          check_failure: null,
        })
      }
      if (url.pathname.startsWith("/plugins/registry/")) {
        const registryId = url.pathname.split("/")[3]
        const entry = registry.find((row) => row.id === registryId)!
        const added = notes({
          id: entry.id,
          name: entry.name,
          source: "registry",
          publisher: entry.publisher,
          hosts: entry.hosts,
          auth_type: entry.auth_type,
        })
        if (entry.auth_type === "oauth") return startSignIn(added)
        connected = [...connected, added]
        return Response.json(added, { status: 201 })
      }
      if (url.pathname === "/plugins/first-party") {
        return Response.json(
          [REDDIT].map((entry) => ({
            ...entry,
            connected: connected.some((plugin) => plugin.id === entry.id),
          }))
        )
      }
      if (url.pathname === "/plugins/first-party/reddit") {
        const added = notes({
          id: "reddit",
          name: "Reddit",
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
        if (customSignsIn) return startSignIn({ ...added, auth_type: "oauth" })
        connected = [...connected, added]
        return Response.json(added, { status: 201 })
      }
      if (url.pathname.endsWith("/key")) {
        if (refuse) {
          const { status, ...detail } = refuse
          return Response.json({ detail }, { status })
        }
        connected = connected.map((plugin) =>
          plugin.id === id
            ? { ...plugin, check_failure: null, disconnected: false }
            : plugin
        )
        return Response.json(connected.find((plugin) => plugin.id === id))
      }
      if (
        url.pathname.endsWith("/disconnect") ||
        url.pathname.endsWith("/connect")
      ) {
        connected = connected.map((plugin) =>
          plugin.id === id
            ? {
                ...plugin,
                check_failure: null,
                disconnected: url.pathname.endsWith("/disconnect"),
              }
            : plugin
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

/** The Electron bridge's way to the user's browser. */
function browser() {
  const openExternal = vi.fn(async () => {})
  window.surfsense = { openExternal } as unknown as typeof window.surfsense
  return openExternal
}

// A sign-in is polled each second; its end shows on the second poll.
const AFTER_POLLS = { timeout: 4000 }

type User = ReturnType<typeof userEvent.setup>

/** Opens a connected plugin's details from the Yours list. */
async function details(user: User, name: string) {
  await user.click(await screen.findByRole("button", { name }))
  return screen.getByRole("region", { name })
}

/** Opens a plugin's actions menu from its details. */
async function actions(user: User, plugin: HTMLElement, name: string) {
  await user.click(
    within(plugin).getByRole("button", { name: `More actions for ${name}` })
  )
  return screen.findByRole("menu")
}

async function browse(user: User) {
  await user.click(await screen.findByRole("tab", { name: "Browse" }))
}

async function yours(user: User) {
  await user.click(screen.getByRole("tab", { name: "Yours" }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("plugins settings", () => {
  it("opens on Yours when a plugin is connected", async () => {
    api()
    render(<PluginsSettings />)

    expect(await screen.findByRole("row", { name: /Notes/ })).toBeTruthy()
    expect(
      screen.getByRole("tab", { name: "Yours" }).getAttribute("aria-selected")
    ).toBe("true")
  })

  it("shows each connected plugin's type and status, failures first", async () => {
    const base = notes()
    api({
      allowed: true,
      plugins: [
        notes(),
        notes({
          id: "reddit",
          name: "Reddit",
          source: "first_party",
          check_failure: "needs_license",
          enabled: false,
        }),
        notes({ id: "wiki", name: "Wiki", source: "registry", enabled: false }),
        notes({
          id: "acme",
          name: "Acme",
          source: "registry",
          removed_reason: "Gone.",
          check_failure: "unreachable",
        }),
        notes({
          id: "docs",
          name: "Docs",
          tools: [{ ...base.tools[0], enabled: false, change: "added" }],
        }),
      ],
    })
    render(<PluginsSettings />)

    const table = await screen.findByRole("table")
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((header) => header.textContent)
    ).toEqual(["Plugin", "Type", "Status"])
    for (const name of [
      "Notes Custom On",
      "Reddit By SurfSense Needs a license",
      "Wiki Third-party Off",
      "Acme Third-party No longer listed",
      "Docs Custom New tools",
    ]) {
      expect(within(table).getByRole("row", { name })).toBeTruthy()
    }
  })

  it("opens a plugin's details in place of the list, and goes back", async () => {
    api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(await screen.findByRole("button", { name: "Notes" }))
    const plugin = screen.getByRole("region", { name: "Notes" })
    expect(within(plugin).getByText("Custom")).toBeTruthy()
    expect(within(plugin).queryByText(/notes\.example/)).toBeNull()
    expect(screen.queryByRole("table")).toBeNull()
    await user.click(screen.getByRole("button", { name: "Back" }))

    expect(screen.getByRole("row", { name: "Notes Custom On" })).toBeTruthy()
    expect(screen.queryByRole("region", { name: "Notes" })).toBeNull()
  })

  it("offers to browse or add a plugin when none is connected", async () => {
    api({ plugins: [] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await screen.findByRole("region", { name: "By SurfSense" })
    await user.click(screen.getByRole("tab", { name: "Yours" }))
    expect(screen.getByText("No plugins connected")).toBeTruthy()
    const panel = screen.getByRole("tabpanel", { name: "Yours" })
    await user.click(
      within(panel).getByRole("button", { name: "Add custom plugin" })
    )
    expect(await screen.findByRole("dialog")).toBeTruthy()
    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())

    await user.click(
      within(panel).getByRole("button", { name: "Browse plugins" })
    )
    expect(
      screen.getByRole("tab", { name: "Browse" }).getAttribute("aria-selected")
    ).toBe("true")
  })

  it("has one Add custom plugin button, beside the tabs on both", async () => {
    api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(await screen.findByRole("button", { name: "Notes" }))
    expect(
      screen.getAllByRole("button", { name: "Add custom plugin" })
    ).toHaveLength(1)
    await user.click(screen.getByRole("tab", { name: "Browse" }))
    await screen.findByRole("region", { name: "By SurfSense" })
    expect(
      screen.getAllByRole("button", { name: "Add custom plugin" })
    ).toHaveLength(1)
    expect(screen.queryByRole("button", { name: "Add MCP server" })).toBeNull()
  })

  it("browses SurfSense’s plugins first, then third-party ones under their switch", async () => {
    api({ allowed: false, registry: [listed()] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(await screen.findByRole("tab", { name: "Browse" }))
    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    const thirdParty = screen.getByRole("region", { name: "Third-party" })
    expect(
      surfsense.compareDocumentPosition(thirdParty) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(
      within(thirdParty).getByText(
        "Plugins from other publishers, and servers you add by URL. Off until you allow them."
      )
    ).toBeTruthy()
    expect(within(thirdParty).queryByRole("list")).toBeNull()

    await user.click(
      within(thirdParty).getByRole("switch", {
        name: "Allow third-party plugins",
      })
    )
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Allow",
      })
    )
    expect(
      await within(thirdParty).findByRole("listitem", { name: "Wiki" })
    ).toBeTruthy()
  })

  it("says a third-party plugin is unused while third-party plugins are off", async () => {
    api({ plugins: [notes({ enabled: false })] })
    render(<PluginsSettings />)

    const row = await screen.findByRole("row", { name: /Notes/ })
    expect(within(row).getByText("Third-party plugins are off")).toBeTruthy()
  })

  it("opens on Browse when nothing is connected", async () => {
    api({ plugins: [] })
    render(<PluginsSettings />)

    await waitFor(() =>
      expect(
        screen
          .getByRole("tab", { name: "Browse" })
          .getAttribute("aria-selected")
      ).toBe("true")
    )
    expect(
      await screen.findByRole("region", { name: "By SurfSense" })
    ).toBeTruthy()
  })

  it("opens on Browse when asked, even with plugins connected", async () => {
    api()
    render(<PluginsSettings start="browse" />)

    expect(
      await screen.findByRole("region", { name: "By SurfSense" })
    ).toBeTruthy()
    expect(
      screen.getByRole("tab", { name: "Browse" }).getAttribute("aria-selected")
    ).toBe("true")
  })

  it("opens with Add custom plugin when asked", async () => {
    api()
    render(<PluginsSettings start="add" />)

    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByLabelText("Server URL")).toBeTruthy()
  })

  it("lists each plugin's tools, the read-only ones apart", async () => {
    api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
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
      await screen.findByRole("button", { name: "Add custom plugin" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Notes")
    await user.type(
      within(dialog).getByLabelText("Server URL"),
      "https://notes.example/mcp"
    )
    await user.type(within(dialog).getByLabelText("Key"), "k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
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
      await screen.findByRole("button", { name: "Add custom plugin" })
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

    const plugin = await details(user, "Notes")
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

  it("says a plugin switched off is off, and leaves on and off to the composer", async () => {
    api({ plugins: [notes({ enabled: false })], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Off")).toBeTruthy()
    const menu = await actions(user, plugin, "Notes")
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent)
    ).toEqual(["Refresh tools", "Remove"])
  })

  it("disconnects only once the user confirms, keeping the plugin to connect again", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(
      within(plugin).getByRole("button", { name: "Disconnect Notes" })
    )
    const confirm = await screen.findByRole("alertdialog")
    expect(changes(calls)).toEqual([])
    await user.click(
      within(confirm).getByRole("button", { name: "Disconnect" })
    )

    expect(await within(plugin).findByText("Disconnected")).toBeTruthy()
    expect(within(plugin).getByRole("button", { name: "Connect" })).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/notes/disconnect", body: null },
    ])
    const menu = await actions(user, plugin, "Notes")
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent)
    ).toEqual(["Remove"])
  })

  it("connects a disconnected plugin again from its row in Yours", async () => {
    const calls = api({
      plugins: [notes({ disconnected: true })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const row = await screen.findByRole("row", { name: "Notes Custom Connect" })
    await user.click(within(row).getByRole("button", { name: "Connect" }))

    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
    expect(screen.queryByRole("region", { name: "Notes" })).toBeNull()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/notes/connect", body: null },
    ])
  })

  it("asks a disconnected plugin with a key for its key to connect again", async () => {
    const calls = api({
      plugins: [notes({ auth_type: "token", disconnected: true })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(within(plugin).getByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog", { name: "Connect Notes" })
    await user.type(within(dialog).getByLabelText("Key"), "k-2")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(plugin).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "PUT", path: "/plugins/notes/key", body: { token: "k-2" } },
    ])
  })

  it("removes a plugin from Yours only once the user confirms", async () => {
    const calls = api({
      plugins: [notes({ disconnected: true })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    const menu = await actions(user, plugin, "Notes")
    await user.click(within(menu).getByRole("menuitem", { name: "Remove" }))
    const confirm = await screen.findByRole("alertdialog")
    expect(changes(calls)).toEqual([])
    await user.click(within(confirm).getByRole("button", { name: "Remove" }))

    expect(await screen.findByText("No plugins connected")).toBeTruthy()
    expect(screen.queryByRole("region", { name: "Notes" })).toBeNull()
    expect(changes(calls)).toEqual([
      { method: "DELETE", path: "/plugins/notes", body: null },
    ])
  })

  it("keeps third-party plugins off until the user allows them", async () => {
    const calls = api()
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(
      within(plugin).getByText("Not used until third-party plugins are allowed")
    ).toBeTruthy()
    await browse(user)
    await user.click(
      await screen.findByRole("switch", { name: "Allow third-party plugins" })
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
    await yours(user)
    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
  })

  it("says a server could not be reached, and checks it again on request", async () => {
    const calls = api({
      plugins: [notes({ check_failure: "unreachable" })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Couldn’t connect")).toBeTruthy()
    const menu = await actions(user, plugin, "Notes")
    await user.click(
      within(menu).getByRole("menuitem", { name: "Refresh tools" })
    )

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

    const plugin = await details(user, "Notes")
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

    const plugin = await details(user, "Notes")
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
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
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
    expect(within(surfsense).getByText("Reddit")).toBeTruthy()
    expect(within(surfsense).getByText("License required")).toBeTruthy()
    // Its icon comes from the list packaged into the app.
    expect(surfsense.querySelector("img")?.getAttribute("src")).toMatch(
      /\/plugins\/first-party\/icons\/reddit$/
    )
    await user.click(within(surfsense).getByRole("button", { name: "Connect" }))

    expect(await within(surfsense).findByText("Connected")).toBeTruthy()
    await yours(user)
    const row = await screen.findByRole("row", {
      name: "Reddit By SurfSense Needs a license",
    })
    expect(row.querySelector("img")?.getAttribute("src")).toMatch(
      /\/plugins\/first-party\/icons\/reddit$/
    )
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/first-party/reddit", body: null },
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

    const expired = await details(user, "Notes")
    expect(within(expired).getByText("License expired")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Back" }))
    const missing = await details(user, "Wiki")
    expect(within(missing).getByText("Needs a license")).toBeTruthy()
    await user.click(
      within(missing).getByRole("button", { name: "License settings" })
    )

    expect(onOpenLicense).toHaveBeenCalledOnce()
  })

  it("fetches nothing from the registry while third-party plugins are off", async () => {
    const calls = api({ registry: [listed()] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await browse(user)
    const section = await screen.findByRole("region", { name: "Third-party" })
    await screen.findByRole("region", { name: "By SurfSense" })
    expect(within(section).queryByRole("listitem")).toBeNull()
    expect(
      calls.some((call) => call.path.startsWith("/plugins/registry"))
    ).toBe(false)
  })

  it("lists the registry's plugins, verified partners and community authors, dated", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [
        listed(),
        listed({
          id: "acme",
          name: "Acme",
          author: "Acme Inc.",
          publisher: "partner",
          verified: true,
          access: "external",
          access_note: "Requires an Acme account.",
        }),
      ],
    })
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    const wiki = await within(section).findByRole("listitem", { name: "Wiki" })
    const acme = within(section).getByRole("listitem", { name: "Acme" })
    expect(within(wiki).getByText("By Jane Doe")).toBeTruthy()
    expect(within(acme).getByText("Verified")).toBeTruthy()
    expect(within(acme).getByText("Requires an Acme account.")).toBeTruthy()
    expect(within(section).getByText("Updated Oct 10, 2026")).toBeTruthy()
  })

  it("connects a registry plugin, asking for its key when it needs one", async () => {
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [
        listed(),
        listed({
          id: "acme",
          name: "Acme",
          auth_type: "token",
          auth_title: "Acme API key",
          auth_description: "Create one under Account › API.",
        }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    const wiki = await within(section).findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))
    expect(await within(wiki).findByText("Connected")).toBeTruthy()

    const acme = within(section).getByRole("listitem", { name: "Acme" })
    await user.click(within(acme).getByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog")
    expect(
      within(dialog).getByText("Create one under Account › API.")
    ).toBeTruthy()
    await user.type(within(dialog).getByLabelText("Acme API key"), "k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(acme).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/wiki", body: null },
      {
        method: "POST",
        path: "/plugins/registry/acme",
        body: { token: "k-1" },
      },
    ])
    await yours(user)
    expect(
      await screen.findByRole("row", { name: "Acme Third-party On" })
    ).toBeTruthy()
  })

  it("connects a registry plugin once the user signs in in the browser", async () => {
    const openExternal = browser()
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [listed({ auth_type: "oauth" })],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const wiki = await screen.findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))

    expect(await within(wiki).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(openExternal).toHaveBeenCalledWith(SIGN_IN_PAGE)
    expect(
      await within(wiki).findByText("Connected", {}, AFTER_POLLS)
    ).toBeTruthy()
    await yours(user)
    expect(
      await screen.findByRole("row", { name: "Wiki Third-party On" })
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/wiki", body: null },
    ])
  })

  it("abandons a sign-in on Cancel", async () => {
    browser()
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [listed({ auth_type: "oauth" })],
      signInEnds: "waiting",
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const wiki = await screen.findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))
    await user.click(
      await within(wiki).findByRole("button", { name: "Cancel" })
    )

    expect(within(wiki).queryByText("Waiting for sign-in…")).toBeNull()
    expect(
      (
        within(wiki).getByRole("button", {
          name: "Connect",
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/wiki", body: null },
      { method: "DELETE", path: "/plugins/sign-ins/s-1", body: null },
    ])
  })

  it("says a sign-in did not finish", async () => {
    browser()
    api({
      plugins: [],
      allowed: true,
      registry: [listed({ auth_type: "oauth" })],
      signInEnds: "failed",
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const wiki = await screen.findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))

    expect(
      await within(wiki).findByRole("alert", {}, AFTER_POLLS)
    ).toHaveProperty("textContent", "The sign-in didn’t finish. Try again.")
    expect(within(wiki).getByRole("button", { name: "Connect" })).toBeTruthy()
  })

  it("adds a server by URL that asks to sign in, once the user has", async () => {
    const openExternal = browser()
    api({ plugins: [], allowed: true, customSignsIn: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Add custom plugin" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Notes")
    await user.type(
      within(dialog).getByLabelText("Server URL"),
      "https://notes.example/mcp"
    )
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(dialog).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(openExternal).toHaveBeenCalledWith(SIGN_IN_PAGE)
    expect(
      await screen.findByRole("row", { name: "Notes Custom On" }, AFTER_POLLS)
    ).toBeTruthy()
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("asks an account's plugin to sign in again, not for a new key", async () => {
    browser()
    const calls = api({
      plugins: [notes({ auth_type: "oauth", check_failure: "sign_in" })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Signed out")).toBeTruthy()
    expect(
      within(plugin).queryByRole("button", { name: "Replace key" })
    ).toBeNull()
    await user.click(
      within(plugin).getByRole("button", { name: "Sign in again" })
    )

    expect(await within(plugin).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(
      await within(plugin).findByText("Connected", {}, AFTER_POLLS)
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/notes/sign-in", body: null },
    ])
  })

  it("asks for SurfSense’s plugin host before listing the registry", async () => {
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [listed()],
      registryHostAllowed: false,
    })
    const user = userEvent.setup()
    render(
      <>
        <PluginsSettings />
        <EgressPrompt />
      </>
    )

    const section = await screen.findByRole("region", { name: "Third-party" })
    await user.click(
      await within(section).findByRole("button", { name: "Allow" })
    )
    const prompt = await screen.findByRole("alertdialog", {
      name: "Allow fetching the list of plugins?",
    })
    await user.click(within(prompt).getByRole("button", { name: "Allow" }))

    expect(
      await within(section).findByRole("listitem", { name: "Wiki" })
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "PUT",
        path: "/egress/host:plugins.surfsense.com",
        body: { enabled: true },
      },
    ])
  })

  it("says why a delisted plugin no longer offers its tools", async () => {
    api({
      plugins: [
        notes({ source: "registry", removed_reason: "The service shut down." }),
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(
      within(plugin).getByText("No longer listed: The service shut down.")
    ).toBeTruthy()
  })
})
