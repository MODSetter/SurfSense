import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { SourcesPanel } from "../sources-panel"
import { useSources } from "../use-sources"
import { useWebSources } from "./use-web-sources"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const LIST =
  "/workspaces/1/documents?document_type=FILE&document_type=NOTE&limit=200&offset=0"
const PAGE = "https://tides.example/explained"
const VIDEO = "https://www.youtube.com/watch?v=tide1"
const CHANNEL = "https://www.youtube.com/@seaschool"

function row(url: string, title: string, fit = "one", puller = "web_page") {
  return {
    url,
    title,
    description: null,
    site: new URL(url).hostname,
    puller,
    fit,
  }
}

const SEARCHED = [
  row(PAGE, "Tide tables explained"),
  row(VIDEO, "Tides in 3 minutes", "one", "youtube"),
  row(CHANNEL, "The Sea School channel", "list", "youtube"),
]

function channelPage(page: number, more: boolean) {
  return {
    link: CHANNEL,
    more,
    failed: false,
    results: [1, 2].map((n) =>
      row(
        `https://www.youtube.com/watch?v=p${page}n${n}`,
        `Tides, page ${page + 1} video ${n}`,
        "one",
        "youtube"
      )
    ),
  }
}

function pending(id: number, url: string) {
  return {
    id,
    title: url,
    document_type: "NOTE" as const,
    mime_type: null,
    status: "pending" as const,
    error_message: null,
    folder_id: null,
    created_at: "2026-10-22T00:00:00Z",
    updated_at: "2026-10-22T00:00:00Z",
  }
}

const onOpenLicense = vi.fn()

function WebHarness() {
  const sources = useSources(1)
  const web = useWebSources(1, sources.addCreated, onOpenLicense)
  return (
    <TooltipProvider>
      <SourcesPanel
        documents={sources.documents}
        selectedDocumentIds={sources.includedDocumentIds}
        highlightedDocumentId={null}
        isLoading={sources.isLoading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={sources.setDocumentIncluded}
        onToggleAll={sources.toggleAllIncluded}
        web={web}
      />
    </TooltipProvider>
  )
}

type Answer = (body: unknown) => Response

let nextId = 20

/** The app's API: a license in `license`, and how each web route answers. */
function serving({
  license = "active",
  search = () => Response.json({ results: SEARCHED }),
  open = (body) => {
    const urls = (body as { urls: string[] }).urls
    return Response.json({
      groups: [
        {
          link: null,
          more: false,
          failed: false,
          results: urls
            .filter((url) => url !== CHANNEL)
            .map((url) => row(url, url)),
        },
        ...(urls.includes(CHANNEL) ? [channelPage(0, true)] : []),
      ].filter((group) => group.results.length > 0),
    })
  },
  list = (body) => {
    const page = (body as { page: number }).page
    return Response.json(channelPage(page, false))
  },
  add = (body) => {
    const urls = (body as { urls: string[] }).urls
    return Response.json(
      {
        created: urls.map((url) => pending(nextId++, url)),
        duplicates: [],
        rejected: [],
      },
      { status: 201 }
    )
  },
}: {
  license?: string
  search?: Answer
  open?: Answer
  list?: Answer
  add?: Answer
} = {}) {
  const sent: { path: string; body: unknown }[] = []
  const routes: Record<string, Answer> = {
    "/workspaces/1/documents/web/search": search,
    "/workspaces/1/documents/web/open": open,
    "/workspaces/1/documents/web/list": list,
    "/workspaces/1/documents/web": add,
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (method === "GET" && path === LIST) return Response.json([])
      if (method === "GET" && path === "/license/status") {
        return Response.json({
          state: license,
          plan: null,
          email: null,
          expiry: null,
          max_users: null,
        })
      }
      if (method === "GET") return Response.json([])
      const body = init?.body ? JSON.parse(String(init.body)) : null
      sent.push({ path, body })
      const answer = routes[path]
      return answer
        ? answer(body)
        : Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return sent
}

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Add sources" }))
  await user.click(
    await screen.findByRole("menuitem", { name: "Add from the web…" })
  )
  return screen.findByRole("dialog", { name: "Add from the web" })
}

function box(dialog: HTMLElement) {
  return within(dialog).getByRole("textbox", {
    name: "Search Google or paste links",
  })
}

async function ask(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
  text: string
) {
  await user.type(box(dialog), text)
  await user.keyboard("{Enter}")
}

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  onOpenLicense.mockReset()
})

describe("adding sources from the web", () => {
  it("adds one search result with its own button and stays open for more", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", {
        name: "Add Tide tables explained",
      })
    )

    expect(await within(dialog).findByText("Added")).toBeTruthy()
    expect(sent).toEqual([
      { path: "/workspaces/1/documents/web/search", body: { query: "tides" } },
      { path: "/workspaces/1/documents/web", body: { urls: [PAGE] } },
    ])
    expect(screen.getByRole("dialog")).toBeTruthy()
    expect(await screen.findByText(PAGE)).toBeTruthy()
  })

  it("adds every result left with Add all, but never a list", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", { name: "Add all (2)" })
    )

    await waitFor(() =>
      expect(within(dialog).getAllByText("Added")).toHaveLength(2)
    )
    expect(sent.at(-1)).toEqual({
      path: "/workspaces/1/documents/web",
      body: { urls: [PAGE, VIDEO] },
    })
  })

  it("opens a list result into its items, and shows more on request", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", {
        name: "Open The Sea School channel",
      })
    )
    expect(
      await within(dialog).findByRole("button", {
        name: "Add Tides, page 1 video 1",
      })
    ).toBeTruthy()
    await user.click(within(dialog).getByRole("button", { name: "Show more" }))

    expect(
      await within(dialog).findByRole("button", {
        name: "Add Tides, page 2 video 2",
      })
    ).toBeTruthy()
    expect(
      within(dialog).queryByRole("button", { name: "Show more" })
    ).toBeNull()
    expect(sent.slice(1)).toEqual([
      { path: "/workspaces/1/documents/web/open", body: { urls: [CHANNEL] } },
      {
        path: "/workspaces/1/documents/web/list",
        body: { url: CHANNEL, page: 1 },
      },
    ])
  })

  it("opens pasted links in the same box instead of searching", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await user.type(
      box(dialog),
      `${PAGE}{Shift>}{Enter}{/Shift}${CHANNEL}{Shift>}{Enter}{/Shift}not a link`
    )
    await user.keyboard("{Enter}")

    expect(
      await within(dialog).findByRole("button", { name: `Add ${PAGE}` })
    ).toBeTruthy()
    expect(
      within(dialog).getByRole("button", { name: "Add Tides, page 1 video 1" })
    ).toBeTruthy()
    expect(within(dialog).getByText("not a link")).toBeTruthy()
    expect(sent).toEqual([
      {
        path: "/workspaces/1/documents/web/open",
        body: { urls: [PAGE, CHANNEL] },
      },
    ])
  })

  it("says a link was already in Sources instead of adding it twice", async () => {
    const user = userEvent.setup()
    serving({
      add: () =>
        Response.json(
          {
            created: [],
            duplicates: [{ url: PAGE, document_id: 3 }],
            rejected: [],
          },
          { status: 201 }
        ),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", {
        name: "Add Tide tables explained",
      })
    )

    expect(await within(dialog).findByText("Already in Sources")).toBeTruthy()
  })

  it("offers a license instead of the search when there is none", async () => {
    const user = userEvent.setup()
    const sent = serving({ license: "none" })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    expect(
      await within(dialog).findByRole("link", { name: /Start a free trial/ })
    ).toBeTruthy()
    expect(
      within(dialog).queryByRole("textbox", {
        name: "Search Google or paste links",
      })
    ).toBeNull()
    await user.click(
      within(dialog).getByRole("button", { name: "License settings" })
    )
    expect(onOpenLicense).toHaveBeenCalled()
    expect(sent).toEqual([])
  })

  it("says so when the license is refused on the way", async () => {
    const user = userEvent.setup()
    serving({
      search: () =>
        Response.json(
          {
            detail: {
              code: "license_refused",
              reason: "expired",
              message: "Adding sources from the web needs a SurfSense license.",
            },
          },
          { status: 403 }
        ),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(
      await within(dialog).findByText(/Your SurfSense license has expired/)
    ).toBeTruthy()
  })

  it("asks to try again when SurfSense can't reach the web", async () => {
    const user = userEvent.setup()
    serving({
      search: () =>
        Response.json(
          {
            detail: {
              code: "plugin_unavailable",
              message: "the plugin's server could not be reached",
            },
          },
          { status: 502 }
        ),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(
      await within(dialog).findByText(/couldn’t reach the web/)
    ).toBeTruthy()
  })
})
