import assert from "node:assert/strict"
import test from "node:test"

import { printOptions } from "./print-options.ts"

test("a Word file prints on the page size and margins its page sets", () => {
  assert.deepEqual(printOptions("docx", "1-4"), {
    preferCSSPageSize: true,
    printBackground: true,
    pageRanges: "1-4",
  })
})

test("a deck prints one slide per page at its slide size, edge to edge", () => {
  assert.deepEqual(printOptions("pptx", "2,5"), {
    preferCSSPageSize: true,
    printBackground: true,
    pageRanges: "2,5",
    margins: { top: 0, bottom: 0, left: 0, right: 0 },
  })
})
