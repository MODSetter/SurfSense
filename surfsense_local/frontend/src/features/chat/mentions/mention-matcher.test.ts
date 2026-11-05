import { describe, expect, it } from "vitest"

import {
  MENTION_TRIGGER,
  mentionAmongNames,
  mentionAt,
} from "./mention-matcher"

describe("the mention at the caret", () => {
  it.each([
    ["@", 1, { query: "", offset: 0, endOffset: 1 }],
    ["check @", 7, { query: "", offset: 6, endOffset: 7 }],
    ["find jobs with @ind", 19, { query: "ind", offset: 15, endOffset: 19 }],
    ["ask @goo about it", 8, { query: "goo", offset: 4, endOffset: 8 }],
    ["ask @goo about it", 6, { query: "g", offset: 4, endOffset: 6 }],
    ["line one\n@not", 13, { query: "not", offset: 9, endOffset: 13 }],
  ])("is found in %j at %i", (text, caret, match) => {
    expect(mentionAt(text, MENTION_TRIGGER, caret)).toEqual(match)
  })

  it.each([
    ["no mention here", 15],
    ["ask @goo about it", 17],
    ["mail me@ind.com", 15],
    ["@goo ", 5],
    ["", 0],
  ])("is not found in %j at %i", (text, caret) => {
    expect(mentionAt(text, MENTION_TRIGGER, caret)).toBeNull()
  })
})

describe("the mention at the caret, among real names", () => {
  const match = mentionAmongNames(["Plan Q3.pdf", "Memo"])
  const at = (text: string) => match(text, MENTION_TRIGGER, text.length)

  it("searches on past a space while the words match a name", () => {
    expect(at("see @plan q")).toEqual({
      query: "plan q",
      offset: 4,
      endOffset: 11,
    })
  })

  it("lets go once the words match none", () => {
    expect(at("see @plan quickly")).toBeNull()
  })

  it("ignores an `@` inside a word", () => {
    expect(at("mail me@plan q")).toBeNull()
  })

  it("stays on the caret's line", () => {
    expect(at("@plan\nq")).toBeNull()
  })

  it("opens straight after a chip", () => {
    expect(at(":source[Memo]{name=document:3}@")).toEqual({
      query: "",
      offset: 30,
      endOffset: 31,
    })
  })
})
