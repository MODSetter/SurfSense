import { afterEach, describe, expect, it } from "vitest"

import { readStartupLayout } from "./startup-layout"

afterEach(() => localStorage.clear())

describe("startup layout", () => {
  it("opens on a new chat with the right panel open when nothing is stored", () => {
    expect(readStartupLayout()).toEqual({
      composer: "center",
      rightPanelOpen: true,
    })
  })

  it("puts the composer at the bottom when the last workspace had a thread open", () => {
    localStorage.setItem("surfsense:last-workspace:v1", "3")
    localStorage.setItem("surfsense:last-thread:3:v1", "12")
    expect(readStartupLayout().composer).toBe("bottom")
  })

  it("centres the composer when the last workspace was on a new chat", () => {
    localStorage.setItem("surfsense:last-workspace:v1", "3")
    localStorage.setItem("surfsense:last-thread:3:v1", "new")
    localStorage.setItem("surfsense:last-thread:4:v1", "12")
    expect(readStartupLayout().composer).toBe("center")
  })

  it("keeps the right panel closed when it was closed", () => {
    localStorage.setItem("surfsense:right-panel:v1", "collapsed")
    expect(readStartupLayout().rightPanelOpen).toBe(false)
  })
})
