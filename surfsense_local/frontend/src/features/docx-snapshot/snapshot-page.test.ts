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

import { DECK_WITH_PICTURE } from "./fixtures/deck-with-picture"
import { LETTER_WITH_LOGO } from "./fixtures/letter-with-logo"
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

const renderer = vi.hoisted(() => ({ load: vi.fn() }))
vi.mock("@silurus/ooxml/docx", () => ({
  DocxDocument: { load: renderer.load },
}))
vi.mock("@silurus/ooxml/math", () => ({ math: {} }))

/** A two-page document, the second page landscape, as the renderer gives it. */
function twoPageDocument() {
  const sizes = [
    { widthPt: 612, heightPt: 792 },
    { widthPt: 792, heightPt: 612 },
  ]
  return {
    pageCount: sizes.length,
    waitUntilLayoutComplete: vi.fn(async () => {}),
    pageSize: (index: number) => sizes[index],
    renderPage: vi.fn(async () => {}),
    destroy: vi.fn(),
  }
}

function pageRules(): string[] {
  const css = [...document.head.querySelectorAll("style")]
    .map((style) => style.textContent ?? "")
    .join("\n")
  return css.match(/@page [^}]*}/g) ?? []
}

describe("layOutSnapshot", () => {
  beforeEach(() => {
    renderer.load.mockReset().mockImplementation(async () => twoPageDocument())
    // jsdom has no canvas to encode.
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
      (callback) => callback(new Blob(["page"], { type: "image/png" }))
    )
  })

  it("draws every page of the Word file with the in-app viewer's renderer", async () => {
    const fetchMock = serve(new Response(LETTER_WITH_LOGO))
    const word = twoPageDocument()
    renderer.load.mockResolvedValue(word)

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBeNull()
    expect(fetchMock).toHaveBeenCalledWith(FILE_URL)
    expect(renderer.load.mock.lastCall![1].showTrackedChanges).toBe(true)
    expect(word.renderPage).toHaveBeenCalledTimes(2)
    expect(document.body.querySelectorAll("img")).toHaveLength(2)
    expect(word.destroy).toHaveBeenCalled()
  })

  it("draws only the pages to be printed, each other page kept in its place", async () => {
    serve(new Response(LETTER_WITH_LOGO))
    const word = twoPageDocument()
    renderer.load.mockResolvedValue(word)

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}&pages=2`,
      document
    )

    expect(failure).toBeNull()
    expect(word.renderPage).toHaveBeenCalledOnce()
    expect(word.renderPage).toHaveBeenCalledWith(
      expect.anything(),
      1,
      expect.anything()
    )
    expect(document.body.querySelectorAll("img")).toHaveLength(1)
    expect(document.body.children).toHaveLength(2)
    expect(pageRules()).toHaveLength(2)
  })

  it("prints each page at its own size, with no margin of its own", async () => {
    serve(new Response(LETTER_WITH_LOGO))

    await layOutSnapshot(`?file=${encodeURIComponent(FILE_URL)}`, document)

    expect(pageRules()).toEqual([
      "@page word-page-0 { size: 612pt 792pt; margin: 0 }",
      "@page word-page-1 { size: 792pt 612pt; margin: 0 }",
    ])
  })

  it("waits for the pages' images before saying it is ready", async () => {
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
      expect(document.body.querySelectorAll("img")).toHaveLength(2)
    )
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(settled).toBe(false)

    imagesLoaded.mockReturnValue(true)
    document.body
      .querySelectorAll("img")
      .forEach((image) => image.dispatchEvent(new Event("load")))

    expect(await ready).toBeNull()
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
    renderer.load.mockRejectedValue(new Error("not an Office file"))

    const failure = await layOutSnapshot(
      `?file=${encodeURIComponent(FILE_URL)}`,
      document
    )

    expect(failure).toBe(
      "the Word file could not be laid out: not an Office file"
    )
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
