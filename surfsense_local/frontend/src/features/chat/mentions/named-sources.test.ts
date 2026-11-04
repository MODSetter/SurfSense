import { describe, expect, it } from "vitest"

import { namedSources } from "./named-sources"

const MEMO = { id: "document:3", label: "Memo" }
const PLAN = { id: "folder:7", label: "Plan Q3" }

describe("what a sent message named", () => {
  it("sends the ids of what is still in the text, files and folders apart", () => {
    expect(
      namedSources([MEMO, PLAN], "compare @Memo with @Plan Q3 please")
    ).toEqual({
      document_ids: [3],
      folder_ids: [7],
    })
  })

  it("drops a pick whose words were deleted", () => {
    expect(namedSources([MEMO, PLAN], "compare @Memo with it")).toEqual({
      document_ids: [3],
      folder_ids: [],
    })
  })

  it("drops a pick edited into another word", () => {
    expect(namedSources([MEMO], "see @Memos")).toBeNull()
  })

  it("keeps a pick at the very end of the text, or before punctuation", () => {
    expect(namedSources([MEMO], "see @Memo")?.document_ids).toEqual([3])
    expect(namedSources([MEMO], "see @Memo, then")?.document_ids).toEqual([3])
  })

  it("sends nothing when nothing was picked", () => {
    expect(namedSources([], "mail me@example.com")).toBeNull()
  })

  it("names a source twice picked once", () => {
    expect(namedSources([MEMO, MEMO], "@Memo and @Memo")?.document_ids).toEqual(
      [3]
    )
  })
})
