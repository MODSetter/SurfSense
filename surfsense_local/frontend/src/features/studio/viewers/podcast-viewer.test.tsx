import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import type { ArtifactDetail } from "../api"
import { PodcastViewer } from "./podcast-viewer"

const seen = vi.hoisted(() => ({ props: [] as Record<string, unknown>[] }))

// Records what each Streamdown render is given; renders the real one.
vi.mock("streamdown", async (original) => {
  const actual = (await original()) as Record<string, unknown>
  const React = await import("react")
  const Real = actual.Streamdown as React.ComponentType<Record<string, unknown>>
  return {
    ...actual,
    Streamdown: (props: Record<string, unknown>) => {
      seen.props.push(props)
      return React.createElement(Real, props)
    },
  }
})

const artifact = {
  id: 1,
  generation: 1,
  content: "## Host\n\nWelcome to **the show**.",
  files: [],
} as unknown as ArtifactDetail

afterEach(cleanup)

describe("podcast viewer", () => {
  it("gives the transcript's Streamdown nothing new when the page around it re-renders", () => {
    const { rerender } = render(<PodcastViewer artifact={artifact} />)
    expect(screen.getByRole("heading", { name: "Host" })).toBeTruthy()

    rerender(<PodcastViewer artifact={artifact} />)

    // Streamdown skips a render whose props are the same objects, and an
    // open transcript is parsed whole on every render it does not skip.
    const [first, second] = seen.props
    for (const key of Object.keys(first)) {
      expect(second[key], key).toBe(first[key])
    }
  })
})
