import { describe, expect, it } from "vitest"

import {
  boxTextOf,
  mentionedSourcesOf,
  messageLength,
  piecesOf,
  sentMessage,
} from "./mention-text"

const MEMO = { id: "document:3", type: "source", label: "Memo" }
const PLAN = { id: "folder:7", type: "source", label: "Plan Q3" }

describe("a message as it is sent", () => {
  it("reads as the user wrote it, and says what it named", () => {
    expect(
      sentMessage(
        "compare :source[Memo]{name=document:3} with :source[Plan Q3]{name=folder:7}"
      )
    ).toEqual({ text: "compare @Memo with @Plan Q3", mentions: [MEMO, PLAN] })
  })

  it("keeps a name that holds a bracket", () => {
    expect(
      sentMessage(':source{label="Report [final]" name="document:3"}').text
    ).toBe("@Report [final]")
  })

  it("names a source chipped twice once", () => {
    const raw = ":source[Memo]{name=document:3} :source[Memo]{name=document:3}"
    expect(sentMessage(raw)).toEqual({ text: "@Memo @Memo", mentions: [MEMO] })
  })

  it("leaves text that only looks like one of its own kind", () => {
    expect(sentMessage("at 12:30[am] and me@example.com")).toEqual({
      text: "at 12:30[am] and me@example.com",
      mentions: [],
    })
  })

  it("counts what the user reads against the limit", () => {
    expect(messageLength(":source[Memo]{name=document:3} ok")).toBe(8)
  })
})

describe("a refused message handed back", () => {
  it("gets its chips back", () => {
    const raw = "compare :source[Memo]{name=document:3} now"
    const { text, mentions } = sentMessage(raw)
    expect(boxTextOf(text, mentions)).toBe(raw)
  })
})

describe("the API's ids", () => {
  it("are files and folders apart", () => {
    expect(mentionedSourcesOf([MEMO, PLAN])).toEqual({
      document_ids: [3],
      folder_ids: [7],
    })
  })

  it("are left out when nothing was named", () => {
    expect(mentionedSourcesOf([])).toBeNull()
  })
})

describe("a sent message's pieces", () => {
  it("sets each named source apart", () => {
    expect(piecesOf("see @Memo and @Plan Q3 now", [MEMO, PLAN])).toEqual([
      "see ",
      MEMO,
      " and ",
      PLAN,
      " now",
    ])
  })

  it("leaves an address that holds the name", () => {
    expect(piecesOf("mail me@Memo.com", [MEMO])).toEqual(["mail me@Memo.com"])
  })

  it("leaves another word that starts the same", () => {
    expect(piecesOf("see @Memos", [MEMO])).toEqual(["see @Memos"])
  })

  it("takes the longer of two names that start alike", () => {
    const short = { id: "document:1", type: "source", label: "Plan" }
    expect(piecesOf("@Plan Q3", [short, PLAN])).toEqual([PLAN])
  })

  it("is the plain text with nothing named", () => {
    expect(piecesOf("mail me@example.com", [])).toEqual(["mail me@example.com"])
  })
})
