import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { Toaster, toast } from "sonner"

import { render } from "@/test-utils"

import { EgressPrompt } from "@/features/egress/egress-prompt"

import type { FirstPartyEntry, Plugin, RegistryEntry } from "./api"
import { PluginsSettings } from "./plugins-settings"

function notes(extra: Partial<Plugin> = {}): Plugin {
  return {
    id: "notes",
    name: "Notes",
    source: "custom",
    url: "https://notes.example/mcp",
    hosts: ["notes.example"],
    auth_type: "none",
    header_names: [],
    transport: "streamable_http",
    needs_scopes: [],
    own_app: false,
    needs_own_app: null,
    never_signed_in: false,
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
    author: "Wiki Project",
    verification: "community",
    verified: false,
    access: "free",
    access_note: null,
    auth_type: "none",
    auth_title: null,
    auth_description: null,
    auth_headers: [],
    user_client: false,
    transport: "streamable_http",
    hosts: ["wiki.example"],
    server_host: "wiki.example",
    sign_in_hosts: [],
    homepage: null,
    privacy_policy: "https://wiki.example/privacy",
    about: null,
    tools: null,
    added: null,
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
  about: "Read whole subreddits, their posts and every comment.",
  tools: ["scrape"],
  added: "2026-10",
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
  customNeedsOwnApp = false,
  signInNeedsOwnApp = false,
  registryNeedsOwnApp = false,
  probe = { transport: "streamable_http", sign_in: "none", tools: 2 },
  probeFails = false,
  signInEnds = "connected",
}: {
  plugins?: Plugin[]
  allowed?: boolean
  refuse?: { status: number; code: string; message: string; name?: string }
  registry?: RegistryEntry[]
  registryHostAllowed?: boolean
  /** Adding by URL reaches a server that asks for OAuth. */
  customSignsIn?: boolean
  /** Adding by URL reaches a provider taking only apps registered in advance. */
  customNeedsOwnApp?: boolean
  /** Signing in again reaches a provider taking only apps registered in advance. */
  signInNeedsOwnApp?: boolean
  /** Connecting a listed OAuth plugin reaches a provider taking only registered apps. */
  registryNeedsOwnApp?: boolean
  /** What Check finds at the URL. */
  probe?: { transport: string; sign_in: string; tools: number | null }
  /** Check reaches nothing at the URL. */
  probeFails?: boolean
  /** What the second poll of a sign-in says; `waiting` never ends. */
  signInEnds?: "connected" | "failed" | "waiting"
} = {}): Call[] {
  const calls: Call[] = []
  let connected = plugins
  // The plugin a sign-in stores once it ends connected, and how often it was polled.
  let signingIn: Plugin | null = null
  let polls = 0
  const startSignIn = (plugin: Plugin) => {
    signingIn = { ...plugin, never_signed_in: false }
    polls = 0
    // Saved at the start, waiting to sign in, as the API keeps it.
    if (!connected.some((saved) => saved.id === plugin.id)) {
      const waiting: Plugin = {
        ...plugin,
        auth_type: "oauth",
        check_failure: "sign_in",
        never_signed_in: true,
        tools: [],
      }
      connected = [...connected, waiting]
    }
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
      // A verdict request keeps its query, which says whether it asked only if stale.
      const asked = url.pathname === LICENSE_CHECK
      calls.push({
        method,
        path: asked ? url.pathname + url.search : url.pathname,
        body,
      })
      if (asked) return new Response(null, { status: 204 })
      const [, , id, , tool] = url.pathname.split("/")
      if (
        url.pathname === "/egress" &&
        init?.method === "PUT" &&
        (body as { destinations?: string[] } | null)?.destinations?.includes(
          "host:plugins.surfsense.com"
        )
      ) {
        hostAllowed = true
        return Response.json([])
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
      if (url.pathname === "/plugins/oauth/redirect-uri") {
        return Response.json({
          redirect_uri: "http://127.0.0.1:8000/plugins/oauth/callback",
        })
      }
      if (url.pathname === `/plugins/${id}/sign-in`) {
        if (signInNeedsOwnApp && !body?.oauth_client) {
          return Response.json(
            {
              detail: {
                code: "plugin_oauth_needs_client",
                message: "This server accepts only apps registered in advance.",
                redirect_uri: "http://127.0.0.1:8000/plugins/oauth/callback",
              },
            },
            { status: 422 }
          )
        }
        return startSignIn({
          ...connected.find((plugin) => plugin.id === id)!,
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
          hosts: entry.hosts,
          auth_type: entry.auth_type,
        })
        // An entry declaring it takes only registered apps is kept before any request.
        if (
          entry.auth_type === "oauth" &&
          (registryNeedsOwnApp || entry.user_client)
        ) {
          const kept = {
            ...added,
            check_failure: "sign_in" as const,
            needs_own_app: "needs_client" as const,
            tools: [],
          }
          connected = [...connected, kept]
          return Response.json(kept, { status: 201 })
        }
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
        if (refuse) {
          const { status, ...detail } = refuse
          return Response.json({ detail }, { status })
        }
        const added = notes({
          id: "reddit",
          name: "Reddit",
          source: "first_party",
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
      if (url.pathname === "/plugins/custom/probe") {
        return probeFails
          ? Response.json(
              {
                detail: {
                  code: "plugin_unreachable",
                  message: "The plugin's server could not be reached.",
                },
              },
              { status: 502 }
            )
          : Response.json(probe)
      }
      if (url.pathname === "/plugins/custom") {
        if (refuse) {
          const { status, ...detail } = refuse
          return Response.json({ detail }, { status })
        }
        const added = notes({ name: body.name, url: body.url })
        if (customNeedsOwnApp) {
          const kept = notes({
            name: body.name,
            url: body.url,
            auth_type: "oauth",
            check_failure: "sign_in",
            needs_own_app: "needs_client",
            tools: [],
          })
          connected = [...connected, kept]
          return Response.json(kept, { status: 201 })
        }
        if (customSignsIn) return startSignIn({ ...added, auth_type: "oauth" })
        connected = [...connected, added]
        return Response.json(added, { status: 201 })
      }
      if (url.pathname.endsWith("/key") || url.pathname.endsWith("/headers")) {
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

const LICENSE_CHECK = "/plugins/license/check"

/** What the user changed: asking the license verdict changes nothing of theirs. */
const changes = (calls: Call[]) =>
  calls.filter(
    (call) => call.method !== "GET" && !call.path.startsWith(LICENSE_CHECK)
  )

/** The Electron bridge's way to the user's browser. */
function browser() {
  const openExternal = vi.fn<(url: string) => Promise<void>>(async () => {})
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

/** Confirms the reminder a community plugin's Connect asks first. */
async function trustCommunity(user: User) {
  const reminder = await screen.findByRole("alertdialog")
  await user.click(within(reminder).getByRole("button", { name: "Connect" }))
}

async function browse(user: User) {
  await user.click(await screen.findByRole("tab", { name: "Browse" }))
}

async function yours(user: User) {
  await user.click(screen.getByRole("tab", { name: "Yours" }))
}

afterEach(() => {
  // Sonner keeps its toasts across tests; one left over would show in the next Toaster.
  toast.dismiss()
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("plugins settings", () => {
  it("asks for the paid plugins' license verdict when opened, if the last is stale", async () => {
    const calls = api()
    render(<PluginsSettings />)

    await waitFor(() =>
      expect(calls).toContainEqual({
        method: "POST",
        path: `${LICENSE_CHECK}?if_stale=true`,
        body: null,
      })
    )
  })

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
      "Docs Custom On New tools",
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

  /** Opens Add custom plugin and fills Name and Server URL. */
  async function addDialog(user: User) {
    await user.click(
      await screen.findByRole("button", { name: "Add custom plugin" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Notes")
    await user.type(
      within(dialog).getByLabelText("Server URL"),
      "https://notes.example/mcp"
    )
    return dialog
  }

  it("connects a server that needs nothing in one click", async () => {
    const calls = api({ plugins: [], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    expect(within(dialog).queryByLabelText("Header value")).toBeNull()
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "POST",
        path: "/plugins/custom",
        body: { url: "https://notes.example/mcp", name: "Notes" },
      },
    ])
  })

  it("sends a key in the header the user names", async () => {
    const calls = api({ plugins: [], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(
      within(dialog).getByRole("button", { name: "Advanced settings" })
    )
    await user.clear(within(dialog).getByLabelText("Header name"))
    await user.type(within(dialog).getByLabelText("Header name"), "x-api-key")
    await user.type(within(dialog).getByLabelText("Header value"), "k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "POST",
        path: "/plugins/custom",
        body: {
          url: "https://notes.example/mcp",
          name: "Notes",
          headers: [{ name: "x-api-key", value: "k-1" }],
        },
      },
    ])
  })

  it("starts with an Authorization header, sent as the user writes it", async () => {
    const calls = api({ plugins: [], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(
      within(dialog).getByRole("button", { name: "Advanced settings" })
    )
    expect(
      (within(dialog).getByLabelText("Header name") as HTMLInputElement).value
    ).toBe("Authorization")
    expect(within(dialog).queryByRole("radio")).toBeNull()
    await user.type(within(dialog).getByLabelText("Header value"), "Bearer k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    await waitFor(() =>
      expect(changes(calls)[0]?.body).toEqual({
        url: "https://notes.example/mcp",
        name: "Notes",
        headers: [{ name: "Authorization", value: "Bearer k-1" }],
      })
    )
  })

  it("opens Advanced settings on the key when the server needs one", async () => {
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

    const dialog = await addDialog(user)
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "This server needs a key. Add one and try again."
    )
    expect(within(dialog).getByLabelText("Header value")).toBeTruthy()
  })

  it("says an address that isn't an MCP server", async () => {
    api({
      plugins: [],
      refuse: {
        status: 422,
        code: "plugin_not_mcp",
        message: "This address doesn't answer as an MCP server.",
      },
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "This address doesn’t answer as an MCP server. Check the URL."
    )
  })

  it("says an address its server retired, rather than that it is not MCP", async () => {
    api({
      plugins: [],
      refuse: {
        status: 422,
        code: "plugin_gone",
        message:
          "This address is no longer served; its server may have moved it.",
      },
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "This address is no longer served; its server may have moved it. Check its documentation for a new one."
    )
  })

  it("starts the sign-in for a server that asks for an account", async () => {
    const openExternal = browser()
    api({ plugins: [], allowed: true, customSignsIn: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    // Add closes; the plugin's details follow the sign-in the browser opened.
    expect(openExternal).toHaveBeenCalledWith(SIGN_IN_PAGE)
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    const plugin = await screen.findByRole("region", { name: "Notes" })
    expect(await within(plugin).findByText("Waiting for sign-in…")).toBeTruthy()
    await waitFor(
      () => expect(within(plugin).queryByText("Not connected")).toBeNull(),
      AFTER_POLLS
    )
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("row", { name: "Notes Custom On" })
    ).toBeTruthy()
  })

  it("keeps a server needing the user's own OAuth app, and opens it to set one up", async () => {
    browser()
    const calls = api({ plugins: [], allowed: true, customNeedsOwnApp: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    // Add closes; the kept plugin's details open, saying what it needs.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    const plugin = await screen.findByRole("region", { name: "Notes" })
    const needs = within(plugin).getByText("Needs an OAuth app")
    expect(needs.className).toContain("text-warning")
    expect(
      within(plugin).getByText("Notes accepts only apps registered with it.")
    ).toBeTruthy()
    await user.click(
      within(plugin).getByRole("button", { name: "Set up OAuth app" })
    )
    const ownApp = await screen.findByRole("dialog", {
      name: "Connect Notes with your own app",
    })
    // Three steps: register an app, give it the callback, paste what it gives.
    expect(
      within(ownApp).getByText("Register an OAuth app with Notes")
    ).toBeTruthy()
    const callback = await within(ownApp).findByLabelText("Callback address")
    await waitFor(() =>
      expect((callback as HTMLInputElement).value).toBe(
        "http://127.0.0.1:8000/plugins/oauth/callback"
      )
    )
    // Not selected on opening: the copy button is how it is copied.
    const field = callback as HTMLInputElement
    expect(field.selectionEnd! - field.selectionStart!).toBe(0)
    const copy = within(ownApp).getByRole("button", {
      name: "Copy the callback address",
    })
    await user.click(copy)
    expect(await navigator.clipboard.readText()).toBe(
      "http://127.0.0.1:8000/plugins/oauth/callback"
    )
    expect(copy.dataset.copied).toBe("true")
    // The tick turns back into the copy icon, as every copy button does.
    await waitFor(() => expect(copy.dataset.copied).toBe("false"), {
      timeout: 4_000,
    })
    // A build signing in on this computer's own port says it changes.
    expect(
      within(ownApp).getByText(/changes each time the app restarts/)
    ).toBeTruthy()
    expect(within(ownApp).queryByLabelText("Scopes")).toBeNull()
    await user.type(within(ownApp).getByLabelText("Client ID"), "own-1")
    await user.type(within(ownApp).getByLabelText("Client secret"), "s-1")
    await user.click(within(ownApp).getByRole("button", { name: "Sign in" }))

    expect(await within(ownApp).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(changes(calls).at(-1)).toEqual({
      method: "POST",
      path: "/plugins/notes/sign-in",
      body: { oauth_client: { client_id: "own-1", client_secret: "s-1" } },
    })
  }, 15_000)

  it("keeps Advanced settings to headers, with no OAuth app", async () => {
    api({ plugins: [], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const dialog = await addDialog(user)
    await user.click(
      within(dialog).getByRole("button", { name: "Advanced settings" })
    )

    expect(within(dialog).getByLabelText("Header value")).toBeTruthy()
    expect(
      within(dialog).queryByRole("button", { name: /OAuth app/ })
    ).toBeNull()
    expect(within(dialog).queryByLabelText("Client ID")).toBeNull()
    expect(within(dialog).queryByLabelText("Callback address")).toBeNull()
  })

  it("edits a custom plugin's connection, asking for the key again", async () => {
    const calls = api({
      plugins: [notes({ auth_type: "headers", header_names: ["x-api-key"] })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(
      within(plugin).getByRole("button", { name: "Edit connection" })
    )
    const dialog = await screen.findByRole("dialog", {
      name: "Edit the connection to Notes",
    })
    expect(
      (within(dialog).getByLabelText("Header name") as HTMLInputElement).value
    ).toBe("x-api-key")
    await user.type(within(dialog).getByLabelText("Header value"), "k-2")
    await user.click(within(dialog).getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: "/plugins/notes/headers",
          body: { headers: [{ name: "x-api-key", value: "k-2" }] },
        },
      ])
    )
  })

  it("asks a disconnected plugin with a key in a header for it to connect again", async () => {
    const calls = api({
      plugins: [
        notes({
          auth_type: "headers",
          header_names: ["Authorization"],
          disconnected: true,
        }),
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(within(plugin).getByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog", { name: "Connect Notes" })
    await user.type(within(dialog).getByLabelText("Header value"), "Bearer k-3")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(plugin).findByText("Connected")).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "PUT",
        path: "/plugins/notes/headers",
        body: { headers: [{ name: "Authorization", value: "Bearer k-3" }] },
      },
    ])
  })

  it("blocks a tool, and lets only a read-only one be always allowed", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(within(plugin).getByRole("radio", { name: "Block count" }))
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
          body: { enabled: true, approval: "always" },
        },
      ])
    )
    expect(
      (
        within(plugin).getByRole("radio", {
          name: "Always allow count",
        }) as HTMLInputElement
      ).disabled
    ).toBe(true)
  })

  it("sets every tool in a group from its menu", async () => {
    const calls = api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    const readOnly = within(plugin).getByRole("group", { name: "Read-only" })
    await user.click(
      within(readOnly).getByRole("button", {
        name: "Permission for every Read-only tool",
      })
    )
    await user.click(
      await screen.findByRole("menuitemradio", { name: "Blocked" })
    )

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: "/plugins/notes/tools/search",
          body: { enabled: false },
        },
      ])
    )
  })

  it("closes a group choice no tool in it can take", async () => {
    const plugin = notes({ source: "first_party" })
    const calls = api({
      plugins: [
        {
          ...plugin,
          tools: plugin.tools.map((tool) =>
            tool.name === "search" ? { ...tool, enabled: false } : tool
          ),
        },
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const card = await details(user, "Notes")
    const readOnly = within(card).getByRole("group", { name: "Read-only" })
    await user.click(
      within(readOnly).getByRole("button", {
        name: "Permission for every Read-only tool",
      })
    )
    const ask = await screen.findByRole("menuitemradio", {
      name: "Needs approval",
    })
    expect(ask.getAttribute("aria-disabled")).toBe("true")
    await user.click(ask)
    expect(changes(calls)).toEqual([])
  })

  it("leaves a tool that cannot take a group choice as it is", async () => {
    const plugin = notes()
    const calls = api({
      plugins: [
        {
          ...plugin,
          tools: [
            ...plugin.tools.map((tool) =>
              tool.name === "count" ? { ...tool, enabled: false } : tool
            ),
            {
              name: "rename",
              title: "Rename note",
              description: "Rename a note.",
              annotations: { destructiveHint: false },
              enabled: false,
              approval: "ask",
              change: null,
            },
          ],
        },
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const card = await details(user, "Notes")
    const others = within(card).getByRole("group", {
      name: "Can make changes",
    })
    await user.click(
      within(others).getByRole("button", {
        name: "Permission for every Can make changes tool",
      })
    )
    await user.click(
      await screen.findByRole("menuitemradio", { name: "Always allow" })
    )

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: "/plugins/notes/tools/rename",
          body: { enabled: true, approval: "always" },
        },
      ])
    )
  })

  it("says Custom when a group's tools differ", async () => {
    const plugin = notes()
    api({
      plugins: [
        {
          ...plugin,
          tools: [
            ...plugin.tools,
            {
              name: "recent",
              title: "Recent notes",
              description: "List the latest notes.",
              annotations: { readOnlyHint: true },
              enabled: false,
              approval: "ask",
              change: null,
            },
          ],
        },
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const card = await details(user, "Notes")
    const readOnly = within(card).getByRole("group", { name: "Read-only" })
    const menu = within(readOnly).getByRole("button", {
      name: "Permission for every Read-only tool",
    })
    expect(menu.textContent).toContain("Custom")
    await user.click(menu)
    expect(
      (
        await screen.findByRole("menuitemradio", { name: "Custom" })
      ).getAttribute("aria-checked")
    ).toBe("true")
  })

  it("folds a group away and back", async () => {
    api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    const fold = within(plugin).getByRole("button", { name: /^Read-only/ })
    await user.click(fold)
    expect(within(plugin).queryByText("Search notes")).toBeNull()
    await user.click(fold)
    expect(within(plugin).getByText("Search notes")).toBeTruthy()
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
    ).toEqual(["Refresh tools", "Submit to the registry", "Remove"])
  })

  it("offers a custom plugin to the registry through the submission form, filled in", async () => {
    api({ allowed: true })
    const openExternal = browser()
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    const menu = await actions(user, plugin, "Notes")
    await user.click(
      within(menu).getByRole("menuitem", { name: "Submit to the registry" })
    )

    const opened = new URL(String(openExternal.mock.calls[0]?.[0]))
    expect(opened.origin + opened.pathname).toBe(
      "https://github.com/MODSetter/SurfSense/issues/new"
    )
    expect(Object.fromEntries(opened.searchParams)).toEqual({
      template: "plugin-submit.yml",
      title: "[plugin submission] Notes",
      name: "Notes",
      url: "https://notes.example/mcp",
    })
  })

  it("never offers a listed plugin to the registry again", async () => {
    api({ plugins: [notes({ source: "registry" })], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    const menu = await actions(user, plugin, "Notes")
    expect(
      within(menu).queryByRole("menuitem", { name: "Submit to the registry" })
    ).toBeNull()
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

    // Saved, its card says what Yours says of it.
    expect(
      await within(surfsense).findByRole("button", { name: "Needs a license" })
    ).toBeTruthy()
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

  it("says in a toast that a plugin connected", async () => {
    api({ plugins: [] })
    const user = userEvent.setup()
    render(
      <>
        <Toaster />
        <PluginsSettings />
      </>
    )

    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    await user.click(within(surfsense).getByRole("button", { name: "Connect" }))

    expect(await screen.findByText("Reddit connected")).toBeTruthy()
  })

  it("says in a toast why a plugin couldn't connect, not beside its button", async () => {
    api({
      plugins: [],
      refuse: {
        status: 502,
        code: "plugin_unreachable",
        message: "unreachable",
      },
    })
    const user = userEvent.setup()
    render(
      <>
        <Toaster />
        <PluginsSettings />
      </>
    )

    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    await user.click(within(surfsense).getByRole("button", { name: "Connect" }))

    expect(await screen.findByText("Couldn’t connect Reddit")).toBeTruthy()
    expect(within(surfsense).queryByRole("alert")).toBeNull()
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

  it("opens a plugin's page from Browse, with its listed tools, before it is connected", async () => {
    api({ plugins: [], allowed: false })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    await user.click(within(surfsense).getByRole("button", { name: "Reddit" }))

    const page = await screen.findByRole("region", { name: "Reddit" })
    expect(within(page).getByText(REDDIT.about)).toBeTruthy()
    expect(within(page).queryByText(REDDIT.description)).toBeNull()
    const tools = within(page).getByRole("region", { name: "Tools" })
    expect(within(tools).getByText("scrape")).toBeTruthy()
    expect(within(page).getByText("Authentication")).toBeTruthy()
    expect(within(page).getByText("SurfSense license")).toBeTruthy()
    expect(within(page).getByText("Publisher")).toBeTruthy()
    expect(within(page).getByText("SurfSense")).toBeTruthy()
    expect(within(page).getByText("Connects to")).toBeTruthy()
    expect(within(page).getByText("October 2026")).toBeTruthy()
    expect(within(page).getByRole("button", { name: "Connect" })).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("region", { name: "By SurfSense" })
    ).toBeTruthy()
  })

  it("says a registry plugin's tools show once connected when its entry lists none", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [
        listed({ about: "Search and read the team wiki.", auth_type: "token" }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    await user.click(
      await within(section).findByRole("button", { name: "Wiki" })
    )

    const page = await screen.findByRole("region", { name: "Wiki" })
    expect(
      within(page).getByText("Search and read the team wiki.")
    ).toBeTruthy()
    expect(
      within(page).getByText("Tools aren’t listed for this plugin.")
    ).toBeTruthy()
    expect(within(page).getByText("API key")).toBeTruthy()
    expect(within(page).getByText("https://wiki.example/privacy")).toBeTruthy()
  })

  it("opens a registry plugin's privacy policy at once, by its id", async () => {
    const openPluginPage = vi.fn(async () => {})
    window.surfsense = {
      openPluginPage,
    } as unknown as typeof window.surfsense
    api({ plugins: [], allowed: true, registry: [listed()] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    await user.click(
      await within(section).findByRole("button", { name: "Wiki" })
    )
    await user.click(
      await screen.findByRole("link", { name: "https://wiki.example/privacy" })
    )

    expect(openPluginPage).toHaveBeenCalledWith("wiki", "privacy_policy")
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("asks before a community plugin connects, and not before a verified one", async () => {
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [
        listed(),
        listed({
          id: "acme",
          name: "Acme",
          author: "Acme Inc.",
          verification: "verified",
          verified: true,
        }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    const wiki = await within(section).findByRole("listitem", { name: "Wiki" })
    expect(within(wiki).getByText("Community")).toBeTruthy()
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))
    const reminder = await screen.findByRole("alertdialog")
    expect(reminder.textContent).toContain(
      "Wiki isn’t verified by SurfSense. Your requests and sign-in go to Wiki Project’s server"
    )
    await user.click(within(reminder).getByRole("button", { name: "Cancel" }))
    expect(changes(calls)).toEqual([])

    const acme = within(section).getByRole("listitem", { name: "Acme" })
    expect(within(acme).getByRole("img", { name: "Verified" })).toBeTruthy()
    await user.click(within(acme).getByRole("button", { name: "Connect" }))
    expect(await within(acme).findByRole("button", { name: "On" })).toBeTruthy()
    expect(screen.queryByRole("alertdialog")).toBeNull()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/acme", body: null },
    ])
  })

  it("says who runs a plugin, and where an account plugin signs in", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [
        listed({
          auth_type: "oauth",
          hosts: ["wiki.example", "accounts.example.com"],
          sign_in_hosts: ["accounts.example.com"],
        }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    await user.click(
      await within(section).findByRole("button", { name: "Wiki" })
    )

    const page = await screen.findByRole("region", { name: "Wiki" })
    expect(within(page).getByText("Wiki Project")).toBeTruthy()
    await user.hover(within(page).getByText("Community"))
    expect(
      await screen.findByText("Community plugin. Not verified by SurfSense.")
    ).toBeTruthy()
    expect(within(page).getByText("Signs in with")).toBeTruthy()
    expect(within(page).getByText("accounts.example.com")).toBeTruthy()
  })

  it("names the service whose account a plugin signs in with", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [listed({ auth_type: "oauth" })],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    await user.click(
      await within(section).findByRole("button", { name: "Wiki" })
    )

    const page = await screen.findByRole("region", { name: "Wiki" })
    expect(within(page).getByText("Your Wiki account")).toBeTruthy()
  })

  it("shows a saved plugin's public page from Browse with its state, which opens it in Yours", async () => {
    api({
      plugins: [notes({ id: "reddit", name: "Reddit", source: "first_party" })],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await browse(user)
    const surfsense = await screen.findByRole("region", {
      name: "By SurfSense",
    })
    await user.click(within(surfsense).getByRole("button", { name: "Reddit" }))

    const page = await screen.findByRole("region", { name: "Reddit" })
    expect(within(page).getByText(REDDIT.about)).toBeTruthy()
    expect(within(page).queryByText(REDDIT.description)).toBeNull()
    expect(within(page).getByText("scrape")).toBeTruthy()
    expect(within(page).queryByRole("switch")).toBeNull()
    expect(within(page).queryByRole("button", { name: "Connect" })).toBeNull()
    await user.click(await within(page).findByRole("button", { name: "On" }))

    // Its settings, in Yours.
    expect(
      screen.getByRole("tab", { name: "Yours" }).getAttribute("aria-selected")
    ).toBe("true")
    const plugin = await screen.findByRole("region", { name: "Reddit" })
    expect(
      within(plugin).getByRole("button", { name: "More actions for Reddit" })
    ).toBeTruthy()
  })

  it("shows a plugin's settings in Yours, with no public details", async () => {
    api({ allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(
      within(plugin).getByRole("radiogroup", { name: /Search notes/ })
    ).toBeTruthy()
    expect(screen.queryByRole("region", { name: "About" })).toBeNull()
    expect(screen.queryByRole("region", { name: "Details" })).toBeNull()
  })

  it("lists the registry's plugins, verified and community ones by their authors, dated", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [
        listed(),
        listed({
          id: "acme",
          name: "Acme",
          author: "Acme Inc.",
          verification: "verified",
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
    expect(within(wiki).getByText("By Wiki Project")).toBeTruthy()
    expect(within(acme).getByRole("img", { name: "Verified" })).toBeTruthy()
    expect(within(acme).getByText("Requires an Acme account.")).toBeTruthy()
    expect(within(section).getByText("Updated Oct 10, 2026")).toBeTruthy()
  })

  it("connects a registry plugin whose key goes in a header its entry names", async () => {
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [
        listed({
          id: "exa",
          name: "Exa",
          verified: true,
          auth_type: "headers",
          auth_headers: [
            {
              name: "x-api-key",
              label: "Exa API key",
              description: "Create one under API keys on exa.ai.",
            },
          ],
        }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    const exa = await within(section).findByRole("listitem", { name: "Exa" })
    await user.click(within(exa).getByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog", { name: "Connect Exa" })
    expect(
      within(dialog).getByText("Create one under API keys on exa.ai.")
    ).toBeTruthy()
    await user.type(within(dialog).getByLabelText("Exa API key"), "k-9")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(exa).findByRole("button", { name: "On" })).toBeTruthy()
    expect(changes(calls)).toEqual([
      {
        method: "POST",
        path: "/plugins/registry/exa",
        body: { headers: [{ name: "x-api-key", value: "k-9" }] },
      },
    ])
  })

  it("saves a registry plugin taking only registered apps, and opens it to set one up", async () => {
    browser()
    const calls = api({
      plugins: [],
      allowed: true,
      registry: [
        listed({
          id: "hub",
          name: "Hub",
          verified: true,
          auth_type: "oauth",
          user_client: true,
        }),
      ],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const section = await screen.findByRole("region", { name: "Third-party" })
    const hub = await within(section).findByRole("listitem", { name: "Hub" })
    await user.click(within(hub).getByRole("button", { name: "Connect" }))

    // Saved at once, and finished in its details in Yours.
    const plugin = await screen.findByRole("region", { name: "Hub" })
    expect(within(plugin).getByText("Needs an OAuth app")).toBeTruthy()
    await user.click(
      within(plugin).getByRole("button", { name: "Set up OAuth app" })
    )
    const ownApp = await screen.findByRole("dialog", {
      name: "Connect Hub with your own app",
    })
    await user.type(within(ownApp).getByLabelText("Client ID"), "own-1")
    await user.click(within(ownApp).getByRole("button", { name: "Sign in" }))

    expect(await within(ownApp).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/hub", body: null },
      {
        method: "POST",
        path: "/plugins/hub/sign-in",
        body: { oauth_client: { client_id: "own-1" } },
      },
    ])
  }, 15_000)

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
    await trustCommunity(user)
    expect(await within(wiki).findByRole("button", { name: "On" })).toBeTruthy()

    const acme = within(section).getByRole("listitem", { name: "Acme" })
    await user.click(within(acme).getByRole("button", { name: "Connect" }))
    await trustCommunity(user)
    const dialog = await screen.findByRole("dialog")
    expect(
      within(dialog).getByText("Create one under Account › API.")
    ).toBeTruthy()
    await user.type(within(dialog).getByLabelText("Acme API key"), "k-1")
    await user.click(within(dialog).getByRole("button", { name: "Connect" }))

    expect(await within(acme).findByRole("button", { name: "On" })).toBeTruthy()
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
    render(
      <>
        <Toaster />
        <PluginsSettings />
      </>
    )

    const wiki = await screen.findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))
    await trustCommunity(user)

    // Saved and opened in Yours, the browser open at once.
    expect(openExternal).toHaveBeenCalledWith(SIGN_IN_PAGE)
    const plugin = await screen.findByRole("region", { name: "Wiki" })
    expect(await within(plugin).findByText("Waiting for sign-in…")).toBeTruthy()
    // The sign-in ends in the browser, so a toast says it worked.
    expect(
      await screen.findByText("Wiki connected", {}, AFTER_POLLS)
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("row", { name: "Wiki Third-party On" })
    ).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/registry/wiki", body: null },
    ])
  })

  it("says a listed plugin was kept to set up, not connected, when it needs the user's own app", async () => {
    api({
      plugins: [],
      allowed: true,
      registry: [listed({ auth_type: "oauth" })],
      registryNeedsOwnApp: true,
    })
    const user = userEvent.setup()
    render(
      <>
        <Toaster />
        <PluginsSettings />
      </>
    )

    const wiki = await screen.findByRole("listitem", { name: "Wiki" })
    await user.click(within(wiki).getByRole("button", { name: "Connect" }))
    await trustCommunity(user)

    expect(
      await screen.findByText("Wiki saved. Set up an OAuth app to connect it.")
    ).toBeTruthy()
    expect(screen.queryByText("Wiki connected")).toBeNull()
    const plugin = await screen.findByRole("region", { name: "Wiki" })
    expect(within(plugin).getByText("Needs an OAuth app")).toBeTruthy()
    expect(
      within(plugin).getByRole("button", { name: "Set up OAuth app" })
    ).toBeTruthy()
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
    await trustCommunity(user)
    const plugin = await screen.findByRole("region", { name: "Wiki" })
    await user.click(
      await within(plugin).findByRole("button", { name: "Cancel" })
    )

    // Kept, signed out, to sign in from here later.
    expect(within(plugin).queryByText("Waiting for sign-in…")).toBeNull()
    expect(within(plugin).getByText("Not connected")).toBeTruthy()
    expect(
      (
        within(plugin).getByRole("button", {
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
    await trustCommunity(user)

    const plugin = await screen.findByRole("region", { name: "Wiki" })
    expect(
      await within(plugin).findByRole("alert", {}, AFTER_POLLS)
    ).toHaveProperty("textContent", "The sign-in didn’t finish.")
    expect(within(plugin).getByRole("button", { name: "Connect" })).toBeTruthy()
  })

  it("offers no OAuth app of the user's own on a plugin that signs in by itself", async () => {
    api({ plugins: [notes({ auth_type: "oauth" })], allowed: true })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(
      within(plugin).queryByRole("button", { name: /own OAuth app/ })
    ).toBeNull()
    const menu = await actions(user, plugin, "Notes")

    expect(
      within(menu).queryByRole("menuitem", { name: /OAuth app/ })
    ).toBeNull()
  })

  it("connects a plugin saved before its first sign-in, with nothing to disconnect", async () => {
    browser()
    const calls = api({
      plugins: [
        notes({
          auth_type: "oauth",
          check_failure: "sign_in",
          never_signed_in: true,
          tools: [],
        }),
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const row = await screen.findByRole("row", {
      name: "Notes Custom Not connected",
    })
    expect(
      within(row).getByText("Not connected").closest("td")?.className
    ).toContain("text-muted-foreground")
    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Connect to see its tools.")).toBeTruthy()
    expect(
      within(plugin).queryByRole("button", { name: "Disconnect Notes" })
    ).toBeNull()
    expect(within(plugin).queryByRole("button", { name: "Sign in" })).toBeNull()
    expect(
      within(plugin).queryByRole("button", { name: /OAuth app/ })
    ).toBeNull()
    await user.click(within(plugin).getByRole("button", { name: "Connect" }))

    expect(await within(plugin).findByText("Waiting for sign-in…")).toBeTruthy()
    expect(changes(calls)).toEqual([
      { method: "POST", path: "/plugins/notes/sign-in", body: null },
    ])
  })

  it("offers no OAuth app of the user's own on a plugin whose sign-in ran out", async () => {
    api({
      plugins: [notes({ auth_type: "oauth", check_failure: "sign_in" })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Needs sign-in").className).toContain(
      "text-warning"
    )
    expect(within(plugin).getByRole("button", { name: "Sign in" })).toBeTruthy()
    expect(
      within(plugin).getByRole("button", { name: "Disconnect Notes" })
    ).toBeTruthy()
    expect(
      within(plugin).queryByRole("button", { name: /OAuth app/ })
    ).toBeNull()
  })

  it("colours a status needing a step amber, and a failure red", async () => {
    api({
      plugins: [
        notes({ auth_type: "oauth", check_failure: "sign_in" }),
        notes({
          id: "wiki",
          name: "Wiki",
          url: "https://wiki.example/mcp",
          check_failure: "unreachable",
        }),
      ],
      allowed: true,
    })
    render(<PluginsSettings />)

    const signIn = await screen.findByRole("cell", { name: "Needs sign-in" })
    const down = screen.getByRole("cell", { name: "Couldn’t connect" })

    expect(signIn.className).toContain("text-warning")
    expect(down.className).toContain("text-destructive")
  })

  it("offers to change the OAuth app of a plugin signed in with the user's own", async () => {
    api({
      plugins: [notes({ auth_type: "oauth", own_app: true })],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(
      within(plugin).getByRole("button", { name: "Change OAuth app" })
    )

    expect(
      await screen.findByRole("dialog", {
        name: "Connect Notes with your own app",
      })
    ).toBeTruthy()
  })

  it("opens the user's own OAuth app when Sign in reaches a server taking only registered ones", async () => {
    api({
      plugins: [notes({ auth_type: "oauth", check_failure: "sign_in" })],
      allowed: true,
      signInNeedsOwnApp: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")
    await user.click(within(plugin).getByRole("button", { name: "Sign in" }))

    const dialog = await screen.findByRole("dialog", {
      name: "Connect Notes with your own app",
    })
    expect(
      within(dialog).getByText(/accepts only apps registered with it/)
    ).toBeTruthy()
  })

  it("says a plugin waiting to sign in shows its tools once signed in", async () => {
    api({
      plugins: [
        notes({ auth_type: "oauth", check_failure: "sign_in", tools: [] }),
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    const plugin = await details(user, "Notes")

    expect(within(plugin).getByText("Sign in to see its tools.")).toBeTruthy()
    expect(within(plugin).queryByText("This server lists no tools.")).toBeNull()
  })

  it("says a plugin whose server wants more access needs it, with Sign in", async () => {
    api({
      plugins: [
        notes({
          auth_type: "oauth",
          check_failure: "sign_in",
          needs_scopes: ["notes:write"],
        }),
      ],
      allowed: true,
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    expect(
      await screen.findByRole("row", { name: "Notes Custom Needs more access" })
    ).toBeTruthy()
    const plugin = await details(user, "Notes")
    expect(within(plugin).getByText("Needs more access")).toBeTruthy()
    expect(within(plugin).getByRole("button", { name: "Sign in" })).toBeTruthy()
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
    expect(within(plugin).getByText("Needs sign-in")).toBeTruthy()
    expect(
      within(plugin).queryByRole("button", { name: "Replace key" })
    ).toBeNull()
    await user.click(within(plugin).getByRole("button", { name: "Sign in" }))

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
        path: "/egress",
        body: { destinations: ["host:plugins.surfsense.com"], enabled: true },
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

/** Types into the search beside the tabs. */
async function search(user: User, text: string) {
  await user.type(
    await screen.findByRole("searchbox", { name: "Search plugins" }),
    text
  )
}

const tabHeld = (name: string) => {
  const tab = screen.getByRole("tab", { name })
  return (
    tab.hasAttribute("disabled") || tab.getAttribute("aria-disabled") === "true"
  )
}

describe("searching plugins", () => {
  it("lists connected plugins first, then the ones to add, from both lists", async () => {
    api({
      allowed: true,
      plugins: [
        notes(),
        notes({ id: "reddit", name: "Reddit", source: "first_party" }),
      ],
      registry: [listed({ id: "redwood", name: "Redwood" })],
    })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await search(user, "red")

    const connected = await screen.findByRole("region", { name: "Yours" })
    const available = await screen.findByRole("region", { name: "Available" })
    expect(within(connected).getByRole("row", { name: /Reddit/ })).toBeTruthy()
    expect(within(connected).queryByRole("row", { name: /Notes/ })).toBeNull()
    expect(
      await within(available).findByRole("listitem", { name: "Redwood" })
    ).toBeTruthy()
    expect(
      within(available).queryByRole("listitem", { name: "Reddit" })
    ).toBeNull()
    expect(
      connected.compareDocumentPosition(available) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it("holds the tabs while searching, and gives them back once cleared", async () => {
    api()
    const user = userEvent.setup()
    render(<PluginsSettings />)
    await screen.findByRole("row", { name: /Notes/ })

    await search(user, "notes")
    expect(tabHeld("Yours")).toBe(true)
    expect(tabHeld("Browse")).toBe(true)

    await user.keyboard("{Escape}")
    expect(
      screen.getByRole<HTMLInputElement>("searchbox", {
        name: "Search plugins",
      }).value
    ).toBe("")
    expect(tabHeld("Yours")).toBe(false)
    expect(
      screen.getByRole("tab", { name: "Yours" }).getAttribute("aria-selected")
    ).toBe("true")
    expect(screen.getByRole("row", { name: /Notes/ })).toBeTruthy()
  })

  it("shows a skeleton, not a spinner, while the search settles", async () => {
    api()
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await search(user, "notes")

    const results = screen.getByRole("region", { name: "Search results" })
    expect(results.querySelector('[data-slot="skeleton"]')).not.toBeNull()
    expect(within(results).queryByRole("status")).toBeNull()
    expect(
      await within(results).findByRole("region", { name: "Yours" })
    ).toBeTruthy()
    expect(results.querySelector('[data-slot="skeleton"]')).toBeNull()
  })

  it("says when nothing matches", async () => {
    api()
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await search(user, "zzz")

    expect(await screen.findByText("No plugins match “zzz”.")).toBeTruthy()
  })

  it("leaves third-party plugins out while they are off, and fetches nothing", async () => {
    const calls = api({ allowed: false, registry: [listed()] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await search(user, "wiki")

    expect(
      await screen.findByText(
        "Third-party plugins aren’t searched until you allow them in Browse."
      )
    ).toBeTruthy()
    expect(screen.queryByRole("listitem", { name: "Wiki" })).toBeNull()
    expect(calls.some((call) => call.path === "/plugins/registry")).toBe(false)
  })

  it("opens a result's page, and goes back to the results", async () => {
    api({ plugins: [] })
    const user = userEvent.setup()
    render(<PluginsSettings />)

    await search(user, "red")
    const available = await screen.findByRole("region", { name: "Available" })
    await user.click(
      await within(available).findByRole("button", { name: "Reddit" })
    )

    const page = await screen.findByRole("region", { name: "Reddit" })
    expect(within(page).getByText(REDDIT.about)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("region", { name: "Available" })
    ).toBeTruthy()
    expect(
      screen.getByRole<HTMLInputElement>("searchbox", {
        name: "Search plugins",
      }).value
    ).toBe("red")
  })
})
