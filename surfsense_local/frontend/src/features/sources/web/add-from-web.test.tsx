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
const VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
const CHANNEL = "https://www.youtube.com/@seaschool"

function row(url: string, title: string, puller = "web_page") {
  return { url, title, description: null, site: new URL(url).hostname, puller }
}

const SEARCHED = [
  row(PAGE, "Tide tables explained"),
  row(VIDEO, "Tides in 3 minutes", "youtube"),
]

/** A search's answer, as the API gives it. */
function found(results: object[], more = false) {
  return Response.json({ results, more })
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

function WebHarness() {
  const sources = useSources(1)
  const web = useWebSources(1, sources.addCreated)
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

/** The app's API: how each web route answers. No license is ever asked for. */
function serving({
  search = () => found(SEARCHED),
  open = (body) => {
    const urls = (body as { urls: string[] }).urls
    return Response.json({
      results: urls.map((url) =>
        row(url, url, url === VIDEO ? "youtube" : "web_page")
      ),
      more: false,
    })
  },
  add = (body) => {
    const urls = (body as { urls: string[] }).urls
    return Response.json(
      { created: urls.map((url) => pending(nextId++, url)), duplicates: [] },
      { status: 201 }
    )
  },
}: {
  search?: Answer
  open?: Answer
  add?: Answer
} = {}) {
  const sent: { path: string; body: unknown }[] = []
  const routes: Record<string, Answer> = {
    "/workspaces/1/documents/web/search": search,
    "/workspaces/1/documents/web/open": open,
    "/workspaces/1/documents/web": add,
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (method === "GET" && path === LIST) return Response.json([])
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

function refused(status: number, detail: object) {
  return () => Response.json({ detail }, { status })
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

// The trigger names where it searches now, so this also checks the one before.
async function pickSite(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
  trigger: string,
  to: string
) {
  await user.click(within(dialog).getByRole("button", { name: trigger }))
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

  it("searches at once with no license, and offers none", async () => {
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(
      await within(dialog).findByRole("button", {
        name: "Add Tide tables explained",
      })
    ).toBeTruthy()
    expect(within(dialog).queryByText(/license/i)).toBeNull()
  })

  it("names a video as YouTube's, since it comes with its transcript", async () => {
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    const video = (
      await within(dialog).findByRole("button", {
        name: "Add Tides in 3 minutes",
      })
    ).closest("li")!
    expect(within(video).getByText("YouTube")).toBeTruthy()
  })

  it("shows each result's whole link, and opens it in the browser once confirmed", async () => {
    // Only the confirmed-link call opens any site; openExternal drops all but SurfSense's own.
    const openConfirmedLink = vi.fn<(url: string) => Promise<void>>(
      async () => undefined
    )
    window.surfsense = { ...window.surfsense!, openConfirmedLink }
    const user = userEvent.setup()
    serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(await within(dialog).findByRole("link", { name: VIDEO }))
    const confirm = await screen.findByRole("dialog", {
      name: "Open www.youtube.com?",
    })
    await user.click(within(confirm).getByRole("button", { name: "Open link" }))

    expect(openConfirmedLink).toHaveBeenCalledExactlyOnceWith(VIDEO)
  })

  it("shows a result's details apart, not joined by a typed dot", async () => {
    const user = userEvent.setup()
    serving({
      search: () =>
        found([
          {
            ...row(PAGE, "Tide tables explained"),
            description: "Mar 3, 2026 · Tides rise twice a day",
          },
        ]),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(await within(dialog).findByText("Mar 3, 2026")).toBeTruthy()
    expect(within(dialog).getByText("Tides rise twice a day")).toBeTruthy()
    expect(within(dialog).queryByText(/·/)).toBeNull()
  })

  it("searches the web unless YouTube is chosen under the box", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await pickSite(user, dialog, "Search the web. Change site.", "YouTube")
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

  it("shows more of a search on request, without repeating a row", async () => {
    const user = userEvent.setup()
    const sent = serving({
      search: (body) =>
        (body as { page: number }).page === 0
          ? found(SEARCHED, true)
          : found([
              row(PAGE, "Tide tables explained"),
              row("https://tides.example/more", "More about tides"),
            ]),
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
      within(dialog).getAllByRole("button", {
        name: "Add Tide tables explained",
      })
    ).toHaveLength(1)
    expect(
      within(dialog).queryByRole("button", { name: "Show more" })
    ).toBeNull()
    expect(sent.at(-1)).toEqual({
      path: "/workspaces/1/documents/web/search",
      body: { query: "tides", source: "web", page: 1 },
    })
  })

  it("opens pasted links as rows, whatever is chosen", async () => {
    const user = userEvent.setup()
    const sent = serving()
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await pickSite(user, dialog, "Search the web. Change site.", "YouTube")
    await ask(user, dialog, PAGE)

    await within(dialog).findByRole("button", { name: `Add ${PAGE}` })
    expect(sent).toEqual([
      { path: "/workspaces/1/documents/web/open", body: { urls: [PAGE] } },
    ])
  })

  it("adds every result left with Add all", async () => {
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
      within(dialog).getByRole("button", { name: `Add ${CHANNEL}` })
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
      await within(dialog).findByRole("button", { name: `Add ${CHANNEL}` })
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
          { created: [], duplicates: [{ url: PAGE, document_id: 3 }] },
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

  it("says when the search server can't be reached, and where to choose another", async () => {
    const user = userEvent.setup()
    serving({
      search: refused(502, {
        code: "search_unreachable",
        host: "searxng.surfsense.com",
        message: "the search server could not be reached",
      }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(
      await within(dialog).findByText(
        "SurfSense couldn’t reach the search server at searxng.surfsense.com. Check your connection, or choose another server in Settings › Network."
      )
    ).toBeTruthy()
  })

  it("says when the search server answered without searching", async () => {
    const user = userEvent.setup()
    serving({
      search: refused(502, {
        code: "search_failed",
        host: "search.firm.example",
        message: "the search server answered without searching",
      }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")

    expect(
      await within(dialog).findByText(
        /The search server at search\.firm\.example didn’t search this time/
      )
    ).toBeTruthy()
  })

  it("names every host still to allow when the network question is declined", async () => {
    const user = userEvent.setup()
    serving({
      add: refused(403, {
        code: "egress_disabled",
        destination: "host:tides.example",
        host: "tides.example",
        hosts: ["tides.example", "www.youtube.com"],
        purpose: "web_page",
        message: "sending data to tides.example is off in Settings > Network",
      }),
    })
    render(<WebHarness />)
    const dialog = await openDialog(user)

    await ask(user, dialog, "tides")
    await user.click(
      await within(dialog).findByRole("button", { name: "Add all (2)" })
    )

    expect(
      await within(dialog).findByText(
        "This needs tides.example and www.youtube.com to be allowed in Settings › Network."
      )
    ).toBeTruthy()
    expect(
      within(dialog).getByRole("button", { name: "Add Tide tables explained" })
    ).toBeTruthy()
  })
})
