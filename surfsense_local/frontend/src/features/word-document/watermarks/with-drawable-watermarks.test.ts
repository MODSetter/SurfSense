/// <reference types="node" />
import { join } from "node:path"

import { createCanvas, GlobalFonts, loadImage } from "@napi-rs/canvas"
import { openDocxDocument } from "@silurus/ooxml/node"
import { strFromU8, unzipSync } from "fflate"
import { describe, expect, it } from "vitest"

import {
  textWatermark,
  WASHED_OUT_PICTURE,
  WORD_TEXT_SHAPE_TYPE,
  wordFileWithHeader,
} from "./fixtures"
import { withDrawableWatermarks } from "./with-drawable-watermarks"

// A machine may have no fonts at all; this one ships with a dependency.
GlobalFonts.registerFromPath(
  join(
    process.cwd(),
    "node_modules/pdfjs-dist/standard_fonts/LiberationSans-Regular.ttf"
  ),
  "Calibri"
)

const factory = {
  createCanvas: (width: number, height: number) => createCanvas(width, height),
  loadImage: async (data: ArrayBuffer | Uint8Array) =>
    loadImage(Buffer.from(data as ArrayBuffer)),
}

/** The first page's pixels, from the real parser and renderer. */
async function pagePixels(file: ArrayBuffer) {
  const session = await openDocxDocument(file, { factory } as never)
  const canvas = (await session.renderPage(0, { width: 612 })) as never as {
    width: number
    height: number
    getContext(kind: "2d"): CanvasRenderingContext2D
  }
  const { data } = canvas
    .getContext("2d")
    .getImageData(0, 0, canvas.width, canvas.height)
  await session.close()
  return data
}

/** How much of the page is not white. */
async function inkOf(file: ArrayBuffer): Promise<number> {
  const data = await pagePixels(file)
  let ink = 0
  for (let i = 0; i < data.length; i += 4) {
    if (data[i] < 250 || data[i + 1] < 250 || data[i + 2] < 250) ink++
  }
  return ink
}

function headerOf(file: ArrayBuffer, part = "word/header1.xml"): string {
  return strFromU8(unzipSync(new Uint8Array(file))[part])
}

function drawn(vml: string): ArrayBuffer {
  return withDrawableWatermarks(wordFileWithHeader(vml))
}

describe("a Word file's watermarks", () => {
  it("draws a text watermark whose fill names a theme colour", async () => {
    const vml =
      WORD_TEXT_SHAPE_TYPE + textWatermark({ fillcolor: "#1f497d [3215]" })
    expect(await inkOf(drawn(vml))).toBeGreaterThan(
      (await inkOf(wordFileWithHeader(""))) + 2000
    )
  })

  it("is what makes that colour draw: the file as written shows nothing", async () => {
    const vml =
      WORD_TEXT_SHAPE_TYPE + textWatermark({ fillcolor: "#1f497d [3215]" })
    const bodyAlone = await inkOf(wordFileWithHeader(""))
    expect(await inkOf(wordFileWithHeader(vml))).toBeLessThan(bodyAlone + 2000)
  })

  it("measures Word's 1pt text at a size that keeps its letters apart", () => {
    const vml = WORD_TEXT_SHAPE_TYPE + textWatermark()
    expect(headerOf(drawn(vml))).toContain("font-size:96pt")
  })

  it("leaves a size the author chose alone", () => {
    const vml = WORD_TEXT_SHAPE_TYPE + textWatermark({ fontSize: "1in" })
    expect(headerOf(drawn(vml))).toContain("font-size:1in")
  })

  it("draws a text watermark whose shape type does not say text may follow its path", async () => {
    const bare = WORD_TEXT_SHAPE_TYPE.replace(/<v:path [^>]*\/>/, "")
    const bodyAlone = await inkOf(wordFileWithHeader(""))
    expect(await inkOf(drawn(bare + textWatermark()))).toBeGreaterThan(
      bodyAlone + 2000
    )
  })

  it("draws a text watermark with no shape type in the file", async () => {
    const bodyAlone = await inkOf(wordFileWithHeader(""))
    expect(await inkOf(drawn(textWatermark()))).toBeGreaterThan(
      bodyAlone + 2000
    )
  })

  it("fades a washed-out picture as Word does, centred on the margins", async () => {
    const data = await pagePixels(drawn(WASHED_OUT_PICTURE))
    // The centre of a 612 x 792 page; the picture is one black pixel, stretched.
    const centre = (396 * 612 + 306) * 4
    // Washout's light grey: 0.3 x 0 + 0.805, per DrawingML's lum.
    expect(data[centre]).toBeGreaterThan(190)
    expect(data[centre]).toBeLessThan(220)
  })

  it("finds a header the document names by any part name", () => {
    const file = wordFileWithHeader(WASHED_OUT_PICTURE, {
      headerPart: "headers/letterhead.xml",
    })
    expect(
      headerOf(withDrawableWatermarks(file), "word/headers/letterhead.xml")
    ).toContain("a:lum")
  })

  it("reads VML under whatever prefix the file gives it", () => {
    const vml = WASHED_OUT_PICTURE.replace(/<(\/?)v:/g, "<$1vml:")
    const file = wordFileWithHeader(vml, { vmlPrefix: "vml" })
    expect(headerOf(withDrawableWatermarks(file))).toContain("a:lum")
  })

  it("leaves a small size alone when the shape type says not to fit the text", () => {
    const fixed = WORD_TEXT_SHAPE_TYPE.replace('fitshape="t"', 'fitshape="f"')
    const vml = fixed + textWatermark({ fontSize: "8pt" })
    expect(headerOf(drawn(vml))).toContain("font-size:8pt")
  })

  it("keeps a washed-out picture's crop", () => {
    const cropped = WASHED_OUT_PICTURE.replace(
      'gain="19661f"',
      'croptop="6554f" cropleft="0.25" gain="19661f"'
    )
    const header = headerOf(drawn(cropped))
    expect(header).toContain("a:lum")
    expect(header).toMatch(/<a:srcRect[^>]* t="10001"/)
    expect(header).toMatch(/<a:srcRect[^>]* l="25000"/)
  })

  it("leaves a washed-out picture in a group as written, with the group's other shapes", () => {
    const group = `<v:group id="Letterhead" style="position:absolute;width:200pt;height:100pt" coordsize="200,100">${WASHED_OUT_PICTURE}<v:rect id="Rule" style="position:absolute;width:200pt;height:2pt" fillcolor="black"/></v:group>`
    const header = headerOf(drawn(group))
    expect(header).toContain('id="Rule"')
    expect(header).toContain('gain="19661f"')
  })

  it("hands back a file with no watermark untouched", () => {
    const file = wordFileWithHeader("")
    expect(withDrawableWatermarks(file)).toBe(file)
  })

  it("hands back a file it cannot read untouched, for the renderer to judge", () => {
    const damaged = new TextEncoder().encode("not a zip").buffer as ArrayBuffer
    expect(withDrawableWatermarks(damaged)).toBe(damaged)
  })
})
