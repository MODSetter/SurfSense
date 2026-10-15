import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"

import type { Artifact } from "./api"
import { ArtifactList } from "./artifact-list"

// Each artifact row shows one compact time; its renders are the row's.
const rendered = vi.hoisted(() => ({ rows: [] as string[] }))

vi.mock("@/components/relative-time", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/components/relative-time")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    RelativeTime: countRenders(actual.RelativeTime, ({ date, compact }) => {
      if (compact) rendered.rows.push(date.toISOString())
    }),
  }
})

function made(id: number, day: number): Artifact {
  return {
    id,
    document_id: 100 + id,
    format: "summary",
    generation: 1,
    title: `Artifact ${id}`,
    status: "ready",
    error_message: null,
    created_at: `2026-09-0${day}T00:00:00.000Z`,
    updated_at: `2026-09-0${day}T00:00:00.000Z`,
    version: null,
    spec_kind: null,
    refinable: false,
  }
}

const first = made(1, 1)
const second = made(2, 2)
const onOpen = vi.fn()
const onRegenerate = vi.fn()
const onCancel = vi.fn()
const onDelete = vi.fn()

function Harness({ artifacts }: { artifacts: Artifact[] }) {
  const [, setRenders] = useState(0)
  return (
    <TooltipProvider>
      <button type="button" onClick={() => setRenders((count) => count + 1)}>
        Render again
      </button>
      <ArtifactList
        workspaceId={1}
        artifacts={artifacts}
        onOpen={onOpen}
        onRegenerate={onRegenerate}
        onCancel={onCancel}
        onDelete={onDelete}
      />
    </TooltipProvider>
  )
}

afterEach(cleanup)

describe("artifact row renders", () => {
  it("renders no row again when the page around the list renders", async () => {
    const user = userEvent.setup()
    render(<Harness artifacts={[first, second]} />)
    rendered.rows.length = 0

    await user.click(screen.getByRole("button", { name: "Render again" }))

    expect(rendered.rows).toEqual([])
  })

  it("renders only the row whose artifact a re-read changed", () => {
    const view = render(<Harness artifacts={[first, second]} />)
    rendered.rows.length = 0

    // A re-read keeps the unchanged artifact's object, as the query's
    // structural sharing does.
    view.rerender(
      <Harness artifacts={[first, { ...second, status: "failed" }]} />
    )

    expect(rendered.rows).toEqual([second.created_at])
  })
})
