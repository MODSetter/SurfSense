// @vitest-environment jsdom
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from "vitest"

import { CLAUSE_WITH_TRACKED_CHANGES } from "./fixtures/clause-with-tracked-changes"
import { DECK_WITH_PICTURE } from "./fixtures/deck-with-picture"
import { LETTER_WITH_HEADER_AND_FOOTER } from "./fixtures/letter-with-header-and-footer"
import { LETTER_WITH_LOGO } from "./fixtures/letter-with-logo"
import { REPORT_WITH_ALT_CHUNK } from "./fixtures/report-with-alt-chunk"
import { layOutSnapshot } from "./snapshot-page"

const FILE_URL = "http://127.0.0.1:8000/artifacts/12/files/primary"
const DECK = `?file=${encodeURIComponent(FILE_URL)}&format=pptx`

function serve(response: Response) {
  const fetchMock = vi.fn(async () => response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function pageRule(): string {
  const css = [...document.head.querySelectorAll("style")]
    .map((style) => style.textContent ?? "")
    .join("\n")
  return css.match(/@page\s*{[^}]*}/)?.[0] ?? ""
}

let imagesLoaded: MockInstance<() => boolean>

beforeEach(() => {
  document.head.replaceChildren()
  document.body.replaceChildren()
  // jsdom loads no images; Chromium has a data URL's loaded at once.
  imagesLoaded = vi
    .spyOn(HTMLImageElement.prototype, "complete", "get")
    .mockReturnValue(true)
  // Nor object URLs, which the deck renderer gives its pictures.
  let objectUrls = 0
  vi.stubGlobal(
    "URL",
    Object.assign(class extends URL {}, {
      createObjectURL: () => `blob:snapshot/${(objectUrls += 1)}`,
      revokeObjectURL: () => {},
    })
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("layOutSnapshot", () => {
  it("lays the Word file out as the in-app viewer's library does", async () => {
    const fetchMock = serve(new Response(LETTER_WITH_LOGO))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBeNull()
    expect(fetchMock).toHaveBeenCalledWith(FILE_URL)
    expect(document.body.textContent).toContain("Client proposal")
    expect(document.body.querySelector("section.docx img")).not.toBeNull()
  })

  it("prints on the document's own page size and margins", async () => {
    serve(new Response(LETTER_WITH_LOGO))

    await layOutSnapshot(`?file=${encodeURIComponent(FILE_URL)}`, document)

    // Twentieths of a point in the file: 12240 x 15840, margins 1440 and 1800.
    expect(pageRule()).toContain("size: 612pt 792pt")
    expect(pageRule()).toContain("margin: 72pt 90pt 72pt 90pt")
  })

  it("waits for the document's images before saying it is ready", async () => {
    serve(new Response(LETTER_WITH_LOGO))
    imagesLoaded.mockReturnValue(false)

    let settled = false
    const ready = layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    ).then((failure) => {
      settled = true
      return failure
    })
    await vi.waitFor(() =>
      expect(document.body.querySelector("section.docx img")).not.toBeNull()
    )
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(settled).toBe(false)

    imagesLoaded.mockReturnValue(true)
    document.body
      .querySelectorAll("img")
      .forEach((image) => image.dispatchEvent(new Event("load")))

    expect(await ready).toBeNull()
  })

  it("leaves out HTML the Word file carries, so none of its script runs", async () => {
    serve(new Response(REPORT_WITH_ALT_CHUNK))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBeNull()
    expect(document.body.textContent).toContain("Quarterly report")
    expect(document.body.querySelector("iframe")).toBeNull()
  })

  it("shows tracked changes, so the agent checks a revised copy as the user sees it", async () => {
    serve(new Response(CLAUSE_WITH_TRACKED_CHANGES))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBeNull()
    expect(document.body.querySelector("ins")?.textContent).toBe("45")
    expect(document.body.querySelector("del")?.textContent).toBe("30")
    expect(
      getComputedStyle(document.body.querySelector("del")!).textDecorationLine
    ).toContain("line-through")
  })

  it("leaves out headers and footers, as the agent is told it does", async () => {
    // Under print pagination docx-preview's header shows once, clipped, on the
    // first page and its footer only after the last line, so a logo there
    // would look misplaced. render_document tells the model they are left out.
    serve(new Response(LETTER_WITH_HEADER_AND_FOOTER))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBeNull()
    expect(document.body.textContent).toContain("Client proposal")
    expect(document.body.textContent).not.toContain("Acme letterhead")
    expect(document.body.textContent).not.toContain("Confidential footer")
  })

  it("says why when the Word file cannot be fetched", async () => {
    serve(new Response("gone", { status: 404 }))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBe("the Word file could not be fetched (HTTP 404)")
  })

  it("says why when the API cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch")
      })
    )

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBe("the Word file could not be fetched: Failed to fetch")
  })

  it("says why when the file is not a Word document", async () => {
    serve(new Response("not a zip at all"))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toMatch(/^the Word file could not be laid out: /)
  })

  it("says why when it was opened without a file", async () => {
    const fetchMock = serve(new Response(LETTER_WITH_LOGO))

    const failure = await layOutSnapshot("", document)

    expect(failure).toBe(
      "the snapshot page was opened without a file to lay out"
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe("layOutSnapshot for a PowerPoint deck", () => {
  // The page loads the deck renderer on demand; its first load here takes
  // longer than a test's time box.
  beforeAll(() => import("./lay-out-deck"), 60_000)

  it("lays every slide out, in order, as the in-app viewer's library does", async () => {
    const fetchMock = serve(new Response(DECK_WITH_PICTURE))

    const failure = await layOutSnapshot(DECK, document)

    expect(failure).toBeNull()
    expect(fetchMock).toHaveBeenCalledWith(FILE_URL)
    expect(document.body.textContent).toMatch(
      /Quarterly review.*Revenue by region.*Next steps/
    )
  })

  it("prints one slide per page at the deck's own slide size", async () => {
    serve(new Response(DECK_WITH_PICTURE))

    await layOutSnapshot(DECK, document)

    // 12192000 x 6858000 EMU in the file, at 96 px to the inch.
    expect(pageRule()).toContain("size: 1280px 720px")
    expect(pageRule()).toContain("margin: 0")
    const slides = [...document.body.children].filter(
      (child) => child.textContent
    )
    expect(slides).toHaveLength(3)
  })

  it("waits for the slides' pictures before saying it is ready", async () => {
    serve(new Response(DECK_WITH_PICTURE))
    imagesLoaded.mockReturnValue(false)

    let settled = false
    const ready = layOutSnapshot(DECK, document).then((failure) => {
      settled = true
      return failure
    })
    await vi.waitFor(() =>
      expect(document.body.querySelector("img")).not.toBeNull()
    )
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(settled).toBe(false)

    imagesLoaded.mockReturnValue(true)
    document.body
      .querySelectorAll("img")
      .forEach((image) => image.dispatchEvent(new Event("load")))

    expect(await ready).toBeNull()
  })

  it("says why when the deck cannot be fetched", async () => {
    serve(new Response("gone", { status: 404 }))

    const failure = await layOutSnapshot(DECK, document)

    expect(failure).toBe("the PowerPoint file could not be fetched (HTTP 404)")
  })

  it("says why when the file is not a PowerPoint deck", async () => {
    serve(new Response("not a zip at all"))

    const failure = await layOutSnapshot(DECK, document)

    expect(failure).toMatch(/^the PowerPoint file could not be laid out: /)
  })

  it("says so when asked for a format it cannot lay out", async () => {
    const fetchMock = serve(new Response(DECK_WITH_PICTURE))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}&format=xlsx`,
      document
    )

    expect(failure).toBe("the snapshot page cannot lay out a xlsx file")
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
