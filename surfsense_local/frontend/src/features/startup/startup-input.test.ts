import { describe, expect, it } from "vitest"

import { createStartupInput } from "./startup-input"

describe("startup input", () => {
  it("hands what was typed during startup to one composer only", () => {
    const input = createStartupInput()
    input.keep("find jobs with @ind", 19)
    expect(input.peek()).toEqual({ text: "find jobs with @ind", caret: 19 })
    input.take()
    expect(input.peek()).toBeNull()
  })

  it("hands over nothing once the text was cleared", () => {
    const input = createStartupInput()
    input.keep("typo", 4)
    input.keep("", 0)
    expect(input.peek()).toBeNull()
  })

  it("is separate for each app, so nothing leaks between them", () => {
    const one = createStartupInput()
    one.keep("find jobs", 9)
    expect(createStartupInput().peek()).toBeNull()
  })

  it("lets startup end at once while nothing is being composed", async () => {
    await expect(createStartupInput().composingEnded()).resolves.toBeUndefined()
  })

  it("holds startup's end until a composition in progress ends", async () => {
    const input = createStartupInput()
    input.setComposing(true)
    let ended = false
    const waiting = input.composingEnded().then(() => {
      ended = true
    })
    await Promise.resolve()
    expect(ended).toBe(false)
    input.setComposing(false)
    await waiting
    expect(ended).toBe(true)
  })
})
