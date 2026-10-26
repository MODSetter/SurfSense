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

/** A search's answer, as the API gives it: one group of rows. */
function found(results: object[], more = false) {
  return Response.json({ link: null, more, failed: false, results })
}

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

type Answer = (body: unknown) => Response | Promise<Response>

let nextId = 20

/** The app's API: a license in `license`, and how each web route answers. */
function serving({
  license = "active",
  search = () => found(SEARCHED),
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
    name: "Search or paste links",
  })
}

// The trigger names the site in use, so this also checks the one before.
async function pickSite(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
  from: string,
  to: string
) {
  await user.click(
    within(dialog).getByRole("button", {
      name: `Search on ${from}. Change site.`,
    })
  )
  await user.click(await screen.findByRole("menuitemradio", { name: to }))
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
      {
        path: "/workspaces/1/documents/web/search",
        body: { query: "tides", source: "web", page: 0 },
      },
      { path: "/workspaces/1/documents/web", body: { urls: [PAGE] } },
    ])
    expect(screen.getByRole("dialog")).toBeTruthy()
    // In Sources, not only in the row that added it.
    await waitFor(() =>
      expect(
        screen.getAllByText(PAGE).some((text) => !dialog.contains(text))
      ).toBe(true)
    )
  })

  it("shows each result's whole link, and opens it in the browser", async () => {
    const openExternal = vi.fn<(url: string) => Promise<void>>(
      async () => undefined
    )
    window.surfsense = { ...window.surfsense!, openExternal }
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(await within(dialog).findByRole("link", { name: VIDEO }))

    expect(openExternal).toHaveBeenCalledExactlyOnceWith(VIDEO)
  })

  it("searches the web unless another site is chosen under the box", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await pickSite(user, dialog, "Google Search", "YouTube")
    await ask(user, dialog, "how tides work")

    await within(dialog).findByRole("button", {
      name: "Add Tide tables explained",
    })
    expect(sent).toEqual([
      {
        path: "/workspaces/1/documents/web/search",
        body: { query: "how tides work", source: "youtube", page: 0 },
      },
    ])
  })

  it("searches the site picked on the start screen", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole("button", { name: "YouTube" }))
    expect(document.activeElement).toBe(box(dialog))
    await ask(user, dialog, "how tides work")

    await within(dialog).findByRole("button", {
      name: "Add Tide tables explained",
    })
    expect(sent).toEqual([
      {
        path: "/workspaces/1/documents/web/search",
        body: { query: "how tides work", source: "youtube", page: 0 },
      },
    ])
  })

  it("shows more of a search on request", async () => {
    const user = userEvent.setup()
    const sent = serving({
      search: (body) =>
        (body as { page: number }).page === 0
          ? found(SEARCHED, true)
          : found([row("https://tides.example/more", "More about tides")]),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, "tides")

    await user.click(
      await within(dialog).findByRole("button", { name: "Show more" })
    )

    expect(
      await within(dialog).findByRole("button", {
        name: "Add More about tides",
      })
    ).toBeTruthy()
    expect(
      within(dialog).getByRole("button", { name: "Add Tide tables explained" })
    ).toBeTruthy()
    expect(sent.at(-1)).toEqual({
      path: "/workspaces/1/documents/web/search",
      body: { query: "tides", source: "web", page: 1 },
    })
  })

  it("opens pasted links by their own site, whatever is chosen", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await pickSite(user, dialog, "Google Search", "Amazon")
    await ask(user, dialog, PAGE)

    await within(dialog).findByRole("button", { name: `Add ${PAGE}` })
    expect(sent).toEqual([
      { path: "/workspaces/1/documents/web/open", body: { urls: [PAGE] } },
    ])
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

  it("lists sources added together newest first, as the server does", async () => {
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", { name: "Add all (2)" })
    )

    // Created in the order asked, so the video got the higher id.
    const video = await screen.findByText(VIDEO, { ignore: "[role=dialog] *" })
    const page = screen.getByText(PAGE, { ignore: "[role=dialog] *" })
    expect(
      video.compareDocumentPosition(page) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it("lets a list be opened again after a new search", async () => {
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", {
        name: "Open The Sea School channel",
      })
    )
    await within(dialog).findByRole("group", { name: "The Sea School channel" })

    await user.clear(box(dialog))
    await ask(user, dialog, "tides")

    const open = await within(dialog).findByRole("button", {
      name: "Open The Sea School channel",
    })
    expect(open.hasAttribute("disabled")).toBe(false)
    expect(open.getAttribute("aria-disabled")).not.toBe("true")
  })

  it("never lets a list that answers after a new search into Add all", async () => {
    const user = userEvent.setup()
    let answerChannel: (response: Response) => void = () => {}
    let searches = 0
    serving({
      search: () =>
        found(
          ++searches === 1
            ? SEARCHED
            : [row("https://moon.example/", "The moon")]
        ),
      open: () =>
        new Promise<Response>((resolve) => {
          answerChannel = resolve
        }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", {
        name: "Open The Sea School channel",
      })
    )

    await user.clear(box(dialog))
    await ask(user, dialog, "moon")
    await within(dialog).findByRole("button", { name: "Add The moon" })
    answerChannel(Response.json({ groups: [channelPage(0, true)] }))

    // The late channel's two videos must not be counted, shown or not.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(
      within(dialog).getByRole("button", { name: "Add all (1)" })
    ).toBeTruthy()
  })

  it("lets a list that failed to open be tried again", async () => {
    const user = userEvent.setup()
    let opens = 0
    serving({
      open: () =>
        Response.json({
          groups: [
            ++opens === 1
              ? { link: CHANNEL, more: false, failed: true, results: [] }
              : channelPage(0, false),
          ],
        }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, "tides")
    const open = await within(dialog).findByRole("button", {
      name: "Open The Sea School channel",
    })

    await user.click(open)
    expect(
      await within(dialog).findByText(
        "Couldn’t open this list. Try again later."
      )
    ).toBeTruthy()
    await user.click(open)

    expect(
      await within(dialog).findByRole("button", {
        name: "Add Tides, page 1 video 1",
      })
    ).toBeTruthy()
  })

  it("ignores a page that answers after the links were opened again", async () => {
    const user = userEvent.setup()
    const pages: number[] = []
    let answerStale: (response: Response) => void = () => {}
    const sent = serving({
      list: (body) => {
        const page = (body as { page: number }).page
        pages.push(page)
        if (pages.length === 1) {
          return new Promise<Response>((resolve) => {
            answerStale = resolve
          })
        }
        return Response.json(channelPage(page, false))
      },
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, CHANNEL)
    let channel = await within(dialog).findByRole("group", { name: CHANNEL })
    await user.click(within(channel).getByRole("button", { name: "Show more" }))

    // The box still holds the link: Enter opens it again.
    await user.click(box(dialog))
    await user.keyboard("{Enter}")
    channel = await within(dialog).findByRole("group", { name: CHANNEL })
    answerStale(Response.json(channelPage(1, false)))
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(
      within(channel).queryByRole("button", {
        name: "Add Tides, page 2 video 1",
      })
    ).toBeNull()
    await user.click(within(channel).getByRole("button", { name: "Show more" }))
    await within(channel).findByRole("button", {
      name: "Add Tides, page 2 video 1",
    })
    expect(pages).toEqual([1, 1])
    expect(sent.filter((s) => s.path.endsWith("/web/open"))).toHaveLength(2)
  })

  it("starts Add all over with each new search", async () => {
    const user = userEvent.setup()
    let answerSecond: (response: Response) => void = () => {}
    let searches = 0
    serving({
      search: () => {
        searches += 1
        if (searches === 1) return found(SEARCHED)
        return new Promise<Response>((resolve) => {
          answerSecond = resolve
        })
      },
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await ask(user, dialog, "tides")
    expect(
      await within(dialog).findByRole("button", { name: "Add all (2)" })
    ).toBeTruthy()

    await user.clear(box(dialog))
    await ask(user, dialog, "moon")

    expect(within(dialog).queryByRole("button", { name: /Add all/ })).toBeNull()
    answerSecond(found([row("https://moon.example/", "The moon")]))
    expect(
      await within(dialog).findByRole("button", { name: "Add all (1)" })
    ).toBeTruthy()
  })

  it("opens a list result into its items, and shows more on request", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    const open = await within(dialog).findByRole("button", {
      name: "Open The Sea School channel",
    })
    await user.click(open)

    // Its items sit together under the row that opened them, named after it.
    const channel = await within(dialog).findByRole("group", {
      name: "The Sea School channel",
    })
    expect(open.closest("li")?.contains(channel)).toBe(true)
    expect(
      within(channel).getByRole("button", { name: "Add Tides, page 1 video 1" })
    ).toBeTruthy()
    await user.click(within(channel).getByRole("button", { name: "Show more" }))

    expect(
      await within(channel).findByRole("button", {
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

  it("shows a video once when the list moved between two pages", async () => {
    const user = userEvent.setup()
    serving({
      // A video posted meanwhile pushed the first page's last one onto this page.
      list: () =>
        Response.json({
          ...channelPage(1, false),
          results: [
            channelPage(0, true).results[1],
            ...channelPage(1, false).results,
          ],
        }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)
    await user.type(box(dialog), CHANNEL)
    await user.keyboard("{Enter}")
    const channel = await within(dialog).findByRole("group", { name: CHANNEL })

    await user.click(within(channel).getByRole("button", { name: "Show more" }))

    expect(
      await within(channel).findByRole("button", {
        name: "Add Tides, page 2 video 1",
      })
    ).toBeTruthy()
    expect(
      within(channel).getAllByRole("button", {
        name: "Add Tides, page 1 video 2",
      })
    ).toHaveLength(1)
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
    const channel = within(dialog).getByRole("group", { name: CHANNEL })
    expect(
      within(channel).getByRole("button", { name: "Add Tides, page 1 video 1" })
    ).toBeTruthy()
    expect(within(dialog).getByText("not a link")).toBeTruthy()
    expect(sent).toEqual([
      {
        path: "/workspaces/1/documents/web/open",
        body: { urls: [PAGE, CHANNEL] },
      },
    ])
  })

  it("opens a link pasted without https://, as browsers copy it", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await user.type(box(dialog), "www.youtube.com/@seaschool")
    expect(
      within(dialog).getByRole("button", { name: "Open links" })
    ).toBeTruthy()
    await user.keyboard("{Enter}")

    expect(
      await within(dialog).findByRole("group", { name: CHANNEL })
    ).toBeTruthy()
    expect(sent).toEqual([
      { path: "/workspaces/1/documents/web/open", body: { urls: [CHANNEL] } },
    ])
  })

  it("searches words that only look like an address", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "node.js tutorial")

    expect(
      await within(dialog).findByRole("button", {
        name: "Add Tide tables explained",
      })
    ).toBeTruthy()
    expect(sent).toEqual([
      {
        path: "/workspaces/1/documents/web/search",
        body: { query: "node.js tutorial", source: "web", page: 0 },
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
        name: "Search or paste links",
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
