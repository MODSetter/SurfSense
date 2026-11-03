import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { StartupRevealProvider } from "./startup-reveal-provider"
import { useStartupReveal } from "./use-startup-reveal"

function Region({ name }: { name: string }) {
  return <div data-testid={name} className={useStartupReveal()} />
}

function LateRegion() {
  const [shown, setShown] = useState(false)
  return shown ? (
    <Region name="late" />
  ) : (
    <button type="button" onClick={() => setShown(true)}>
      show
    </button>
  )
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe("startup reveal", () => {
  it("fades in what the dashboard first draws after a visible wait", () => {
    render(
      <StartupRevealProvider reveal>
        <Region name="region" />
      </StartupRevealProvider>
    )
    expect(screen.getByTestId("region").className).toContain("ss-reveal")
  })

  it("draws it at once after a wait too short to see", () => {
    render(
      <StartupRevealProvider reveal={false}>
        <Region name="region" />
      </StartupRevealProvider>
    )
    expect(screen.getByTestId("region").className).not.toContain("ss-reveal")
  })

  it("stops fading once the fade is over, so later contents arrive as usual", () => {
    vi.useFakeTimers()
    render(
      <StartupRevealProvider reveal>
        <Region name="region" />
      </StartupRevealProvider>
    )
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByTestId("region").className).not.toContain("ss-reveal")
  })

  it("never fades what mounts after startup", async () => {
    render(
      <StartupRevealProvider reveal>
        <LateRegion />
      </StartupRevealProvider>
    )
    await userEvent.click(screen.getByRole("button", { name: "show" }))
    expect(screen.getByTestId("late").className).not.toContain("ss-reveal")
  })

  it("fades nothing outside startup", () => {
    render(<Region name="region" />)
    expect(screen.getByTestId("region").className).not.toContain("ss-reveal")
  })
})
