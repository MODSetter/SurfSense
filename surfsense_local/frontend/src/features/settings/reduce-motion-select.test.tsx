import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MOTION_PREFERENCE_KEY } from "@/features/motion-preference/motion-preference"

import { ReduceMotionSelect } from "./reduce-motion-select"

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal("matchMedia", () => ({ matches: false }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.documentElement.classList.remove("reduce-motion")
})

describe("ReduceMotionSelect", () => {
  it("offers Match system, On and Off, and starts on Match system", () => {
    render(<ReduceMotionSelect aria-label="Reduce motion" />)

    const select = screen.getByRole<HTMLSelectElement>("combobox", {
      name: "Reduce motion",
    })
    expect(select.value).toBe("system")
    expect(
      screen.getAllByRole("option").map((option) => option.textContent)
    ).toEqual(["Match system", "On", "Off"])
  })

  it("shows the saved choice", () => {
    localStorage.setItem(MOTION_PREFERENCE_KEY, "off")
    render(<ReduceMotionSelect aria-label="Reduce motion" />)

    expect(
      screen.getByRole<HTMLSelectElement>("combobox", {
        name: "Reduce motion",
      }).value
    ).toBe("off")
  })

  it("reduces motion as soon as On is picked", async () => {
    const user = userEvent.setup()
    render(<ReduceMotionSelect aria-label="Reduce motion" />)

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Reduce motion" }),
      "on"
    )

    expect(document.documentElement.classList.contains("reduce-motion")).toBe(
      true
    )
    expect(localStorage.getItem(MOTION_PREFERENCE_KEY)).toBe("on")
  })
})
