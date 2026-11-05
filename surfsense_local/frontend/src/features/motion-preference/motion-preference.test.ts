import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest"

import indexHtml from "../../../index.html?raw"

import {
  followMotionPreference,
  MOTION_PREFERENCE_KEY,
  motionIsReduced,
  readMotionPreference,
  setMotionPreference,
} from "./motion-preference"

const CLASS = "reduce-motion"
const root = document.documentElement

function osAsksToReduce(matches: boolean) {
  const listeners = new Set<() => void>()
  const query = {
    matches,
    addEventListener: (_: string, listener: () => void) =>
      listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) =>
      listeners.delete(listener),
  }
  vi.stubGlobal("matchMedia", (text: string) =>
    text.includes("reduced-motion") ? query : { matches: false }
  )
  return {
    change(next: boolean) {
      query.matches = next
      listeners.forEach((listener) => listener())
    },
  }
}

// The cases every reader must agree on: [saved choice, OS asks, reduced].
const CASES: [string | null, boolean, boolean][] = [
  [null, false, false],
  [null, true, true],
  ["system", false, false],
  ["system", true, true],
  ["on", false, true],
  ["on", true, true],
  ["off", false, false],
  ["off", true, false],
  ["nonsense", true, true],
  ["nonsense", false, false],
]

function save(value: string | null) {
  if (value !== null) localStorage.setItem(MOTION_PREFERENCE_KEY, value)
}

beforeEach(() => {
  localStorage.clear()
  root.classList.remove(CLASS)
})

afterEach(() => {
  vi.unstubAllGlobals()
  root.classList.remove(CLASS, "light", "dark")
})

describe("motion preference", () => {
  it.each(CASES)(
    "with %s saved and the OS asking %s, reduced is %s",
    (saved, asks, reduced) => {
      save(saved)
      osAsksToReduce(asks)

      expect(motionIsReduced()).toBe(reduced)
      followMotionPreference()
      expect(root.classList.contains(CLASS)).toBe(reduced)
    }
  )

  it.each(CASES)(
    "index.html's first-frame script agrees with %s saved and the OS asking %s",
    (saved, asks, reduced) => {
      save(saved)
      osAsksToReduce(asks)

      const script = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? ""
      new Function(script)()

      expect(root.classList.contains(CLASS)).toBe(reduced)
    }
  )

  it("takes effect at once when the choice changes, and survives a reload", () => {
    osAsksToReduce(false)

    setMotionPreference("on")
    expect(root.classList.contains(CLASS)).toBe(true)
    expect(motionIsReduced()).toBe(true)

    setMotionPreference("off")
    expect(root.classList.contains(CLASS)).toBe(false)
    expect(localStorage.getItem(MOTION_PREFERENCE_KEY)).toBe("off")
  })

  it("still applies a choice storage refuses to keep", () => {
    osAsksToReduce(false)
    const write = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("blocked", "SecurityError")
      })
    onTestFinished(() => {
      write.mockRestore()
      setMotionPreference("system")
    })

    setMotionPreference("on")

    expect(root.classList.contains(CLASS)).toBe(true)
    expect(motionIsReduced()).toBe(true)
    expect(readMotionPreference()).toBe("on")
  })

  it("follows the OS while it matches the system, and ignores it otherwise", () => {
    const os = osAsksToReduce(false)
    followMotionPreference()

    os.change(true)
    expect(root.classList.contains(CLASS)).toBe(true)

    setMotionPreference("off")
    os.change(true)
    expect(root.classList.contains(CLASS)).toBe(false)
  })

  it("follows a choice made in another tab", () => {
    osAsksToReduce(false)
    followMotionPreference()

    localStorage.setItem(MOTION_PREFERENCE_KEY, "on")
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: MOTION_PREFERENCE_KEY,
        storageArea: localStorage,
      })
    )

    expect(root.classList.contains(CLASS)).toBe(true)
  })
})
