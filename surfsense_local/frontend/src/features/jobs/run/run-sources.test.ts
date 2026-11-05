import { describe, expect, it } from "vitest"

import { source, workbook } from "../stub-jobs-api"

import {
  chosenPolicies,
  defaultWorkbook,
  isWorkbook,
  policyChoices,
  sourcesReading,
  workbookChoices,
  workbooksReading,
} from "./run-sources"

const sources = [
  workbook(2, "Old questionnaire.xlsx"),
  source(3, "Security policy.pdf"),
  workbook(7, "Vendor questionnaire.xlsx"),
  workbook(8, "Still reading.xlsx", { status: "processing" }),
  source(9, "Notes", { document_type: "NOTE", mime_type: null }),
  source(10, "Uploading.pdf", { status: "pending" }),
  // An Excel file of an older kind is not a workbook a job can fill in.
  source(11, "Legacy.xls", { mime_type: "application/vnd.ms-excel" }),
]

describe("run sources", () => {
  it("offers only ready Excel workbooks, newest first", () => {
    expect(workbookChoices(sources).map((each) => each.id)).toEqual([7, 2])
    expect(workbooksReading(sources)).toBe(1)
    expect(
      isWorkbook(source(12, "Renamed", { mime_type: sources[0].mime_type }))
    ).toBe(true)
  })

  it("starts on the newest workbook ticked in the sidebar, else the newest", () => {
    const choices = workbookChoices(sources)

    expect(defaultWorkbook(choices, [2, 3])).toBe(2)
    expect(defaultWorkbook(choices, [3])).toBe(7)
    expect(defaultWorkbook([], [3])).toBeNull()
  })

  it("leaves the workbook out of the documents to answer from", () => {
    expect(policyChoices(sources, 7).map((each) => each.id)).toEqual([
      2, 3, 9, 11,
    ])
    expect(sourcesReading(sources)).toBe(1)
  })

  it("starts with the sources ticked in the sidebar, except other workbooks", () => {
    const choices = policyChoices(sources, 7)

    expect(chosenPolicies(choices, new Map(), [2, 3, 7])).toEqual([3])
  })

  it("keeps the user’s own ticks over the sidebar’s", () => {
    const choices = policyChoices(sources, 7)
    const marks = new Map([
      [2, true],
      [3, false],
      [9, true],
    ])

    expect(chosenPolicies(choices, marks, [3])).toEqual([2, 9])
  })
})
