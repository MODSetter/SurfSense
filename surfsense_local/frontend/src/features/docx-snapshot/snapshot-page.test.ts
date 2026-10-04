// @vitest-environment jsdom
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from "vitest"

import { LETTER_WITH_LOGO } from "./fixtures/letter-with-logo"
import { REPORT_WITH_ALT_CHUNK } from "./fixtures/report-with-alt-chunk"
import { layOutSnapshot } from "./snapshot-page"

const FILE_URL = "http://127.0.0.1:8000/artifacts/12/files/primary"

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
