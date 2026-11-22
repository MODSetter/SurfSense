/// <reference types="node" />
import { readFileSync } from "node:fs"
import { join } from "node:path"

import { createCanvas, GlobalFonts, loadImage } from "@napi-rs/canvas"
import { materializeXlsxWorkbook, openDocxDocument } from "@silurus/ooxml/node"
import { describe, expect, it } from "vitest"

import { withDrawableWatermarks } from "../watermarks/with-drawable-watermarks"

// Files the agent's own paths wrote: a python-docx script, then the revision
// engine on its result, and the documents skill's workbook example. Each goes
// through the real parser and renderer, so a bump of either that loses what a
// user would see in the download fails here.
const HERE = "src/features/word-document/agent-made-files"
const file = (name: string): ArrayBuffer => {
  const bytes = readFileSync(join(process.cwd(), HERE, name))
  return bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer
}

// A machine may have no fonts at all; one shipped with a dependency stands in for
// every family these files name, as only their text is asserted, not its metrics.
for (const family of [
  "Calibri",
  "Cambria",
  "Arial",
  "Times New Roman",
  "Aptos",
]) {
  GlobalFonts.registerFromPath(
    join(
      process.cwd(),
      "node_modules/pdfjs-dist/standard_fonts/LiberationSans-Regular.ttf"
    ),
    family
  )
}

const factory = {
  createCanvas: (width: number, height: number) => createCanvas(width, height),
  loadImage: async (data: ArrayBuffer | Uint8Array) =>
    loadImage(Buffer.from(data as ArrayBuffer)),
}

/** The text on every page, as drawn. */
async function pagesOf(name: string): Promise<string[]> {
  const session = await openDocxDocument(withDrawableWatermarks(file(name)), {
    factory,
  } as never)
  const pages: string[] = []
  for (let index = 0; index < session.pageCount; index++) {
    const runs: string[] = []
    await session.renderPage(index, {
      width: 612,
      onTextRun: (run) => runs.push(run.text),
    })
    pages.push(runs.join(""))
  }
  await session.close()
  return pages
}

describe("what the agent makes, as a user opens it", () => {
  it("numbers a scripted report's pages and repeats its header on each", async () => {
    const pages = await pagesOf("scripted-report.docx")
    expect(pages.length).toBeGreaterThan(1)
    pages.forEach((page, index) => {
      expect(page).toContain(`Page ${index + 1} of ${pages.length}`)
    })
    expect(pages[0]).toContain("ACME report")
    expect(pages[1]).toContain("ACME report")
  })

  it("keeps a scripted report's tables and mixed scripts", async () => {
    const [first] = await pagesOf("scripted-report.docx")
    expect(first).toContain("Merged across three")
    expect(first).toContain("日本語")
  })

  it("shows a revised copy's insertion", async () => {
    const pages = await pagesOf("revised-copy.docx")
    expect(pages.join("")).toContain("A newly inserted paragraph")
  })

  it("keeps a workbook's formatted values, sheet and chart", async () => {
    const { worksheets } = await materializeXlsxWorkbook(
      file("skill-workbook.xlsx")
    )
    const text = JSON.stringify(worksheets[0])
    expect(text).toContain("Rollout")
    expect(text).toContain("Total")
    expect(text).toContain("Cost by phase")
  })
})
