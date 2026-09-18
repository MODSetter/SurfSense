import ExcelJS from "exceljs"
import { describe, expect, it } from "vitest"

import {
  MAX_DISPLAY_ROWS,
  MAX_VIEWER_BYTES,
  ParseWorkbookError,
  parseWorkbook,
} from "./parse-workbook"

async function workbookBytes(
  build: (wb: ExcelJS.Workbook) => void | Promise<void>
): Promise<ArrayBuffer> {
  const wb = new ExcelJS.Workbook()
  await build(wb)
  return (await wb.xlsx.writeBuffer()) as ArrayBuffer
}

describe("parseWorkbook", () => {
  it("formats values and formula caches", async () => {
    const data = await workbookBytes((wb) => {
      const sheet = wb.addWorksheet("Budget")
      sheet.getCell("A1").value = "Item"
      sheet.getCell("B1").value = "Amount"
      sheet.getCell("A2").value = "Widgets"
      sheet.getCell("B2").value = 12.5
      sheet.getCell("B2").numFmt = "0.00"
      sheet.getCell("B3").value = { formula: "B2*2", result: 25 }
      sheet.getCell("B3").numFmt = "0.00"
    })

    const view = await parseWorkbook(data)
    expect(view.sheets.length).toBe(1)
    expect(view.sheets[0].name).toBe("Budget")
    expect(view.sheets[0].truncated).toBe(false)
    expect(view.sheets[0].cells[0][0].text).toBe("Item")
    expect(view.sheets[0].cells[1][1].text).toBe("12.50")
    expect(view.sheets[0].cells[2][1].text).toBe("25.00")
  })

  it("caps displayed rows", async () => {
    const data = await workbookBytes((wb) => {
      const sheet = wb.addWorksheet("Big")
      for (let row = 1; row <= MAX_DISPLAY_ROWS + 3; row += 1) {
        sheet.getCell(row, 1).value = row
      }
    })

    const view = await parseWorkbook(data)
    expect(view.sheets[0].cells.length).toBe(MAX_DISPLAY_ROWS)
    expect(view.sheets[0].truncated).toBe(true)
  })

  it("rejects oversize payloads before parsing", async () => {
    const huge = new ArrayBuffer(MAX_VIEWER_BYTES + 1)
    await expect(parseWorkbook(huge)).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof ParseWorkbookError && error.code === "oversize"
    )
  })

  it("rejects corrupt workbooks", async () => {
    const corrupt = new TextEncoder().encode("not-a-workbook").buffer
    await expect(parseWorkbook(corrupt)).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof ParseWorkbookError && error.code === "corrupt"
    )
  })
})
