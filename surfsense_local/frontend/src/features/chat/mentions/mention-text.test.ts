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
  it("reads as the user wrote it, and says where each chip is", () => {
    expect(
      sentMessage(
        "compare :source[Memo]{name=document:3} with :source[Plan Q3]{name=folder:7}"
      )
    ).toEqual({
      text: "compare @Memo with @Plan Q3",
      mentions: [
        { ...MEMO, at: 8, length: 5 },
        { ...PLAN, at: 19, length: 8 },
      ],
    })
  })

  it("keeps a name that holds a bracket", () => {
    expect(
      sentMessage(':source{label="Report [final]" name="document:3"}').text
    ).toBe("@Report [final]")
  })

  it("keeps each chip of one source", () => {
    const raw = ":source[Memo]{name=document:3} :source[Memo]{name=document:3}"
    expect(sentMessage(raw)).toEqual({
      text: "@Memo @Memo",
      mentions: [
        { ...MEMO, at: 0, length: 5 },
        { ...MEMO, at: 6, length: 5 },
      ],
    })
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

  it("keeps two sources of one title apart", () => {
    const raw = ":source[Memo]{name=document:3} :source[Memo]{name=document:4}"
    const { text, mentions } = sentMessage(raw)
    expect(boxTextOf(text, mentions)).toBe(raw)
  })

  it("leaves a typed name as text beside a chip of that name", () => {
    const raw = "typed @Memo and :source[Memo]{name=document:3}"
    const { text, mentions } = sentMessage(raw)
    expect(boxTextOf(text, mentions)).toBe(raw)
  })
})

describe("the API's ids", () => {
  it("are files and folders apart, each once, with each chip's place", () => {
    expect(
      mentionedSourcesOf([
        { ...MEMO, at: 0, length: 5 },
        { ...MEMO, at: 6, length: 5 },
        { ...PLAN, at: 12, length: 8 },
      ])
    ).toEqual({
      document_ids: [3],
      folder_ids: [7],
      chips: [
        { id: "document:3", at: 0, length: 5 },
        { id: "document:3", at: 6, length: 5 },
        { id: "folder:7", at: 12, length: 8 },
      ],
    })
  })

  it("are left out when nothing was named", () => {
    expect(mentionedSourcesOf([])).toBeNull()
  })
})

describe("a sent message's pieces", () => {
  const memo = { ...MEMO, at: 4, length: 5 }

  it("sets each chip apart by where it is", () => {
    const plan = { ...PLAN, at: 14, length: 8 }
    expect(piecesOf("see @Memo and @Plan Q3 now", [plan, memo])).toEqual([
      "see ",
      memo,
      " and ",
      plan,
      " now",
    ])
  })

  it("leaves a typed name of the same title as text", () => {
    expect(piecesOf("see @Memo, not @Memo", [memo])).toEqual([
      "see ",
      memo,
      ", not @Memo",
    ])
  })

  it("shows a source renamed since under its new name", () => {
    const renamed = { ...memo, label: "Memo final" }
    expect(piecesOf("see @Memo now", [renamed])).toEqual([
      "see ",
      renamed,
      " now",
    ])
  })

  it("is plain text when a place no longer fits the text", () => {
    expect(piecesOf("see", [memo])).toEqual(["see"])
    expect(piecesOf("no chip at this place", [memo])).toEqual([
      "no chip at this place",
    ])
  })

  it("is the plain text with nothing named", () => {
    expect(piecesOf("mail me@example.com", [])).toEqual(["mail me@example.com"])
  })
})
