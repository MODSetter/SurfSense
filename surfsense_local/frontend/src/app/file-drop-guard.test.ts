import { afterEach, describe, expect, it } from "vitest"

import { guardFileDrops } from "./file-drop-guard"

function fileDrag(type: "dragover" | "drop") {
  const event = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(event, "dataTransfer", {
    value: { types: ["Files"], dropEffect: "copy" },
  })
  return event
}

let release: () => void = () => {}
afterEach(() => release())

describe("file drop guard", () => {
  it("keeps a file dropped outside a drop target from replacing the app", () => {
    release = guardFileDrops(window)

    const over = fileDrag("dragover")
    const drop = fileDrag("drop")
    document.body.dispatchEvent(over)
    document.body.dispatchEvent(drop)

    // Unhandled, Chromium opens the file in the window, which in Electron
    // navigates away from the app entirely.
    expect(over.defaultPrevented).toBe(true)
    expect(drop.defaultPrevented).toBe(true)
  })

  it("leaves drags that carry no files alone", () => {
    release = guardFileDrops(window)
    const text = new Event("drop", { bubbles: true, cancelable: true })
    Object.defineProperty(text, "dataTransfer", {
      value: { types: ["text/plain"] },
    })

    document.body.dispatchEvent(text)

    expect(text.defaultPrevented).toBe(false)
  })
})
