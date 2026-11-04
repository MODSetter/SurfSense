import { describe, expect, it } from "vitest"

import { MENTION_TRIGGER, mentionAt } from "./mention-matcher"

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
