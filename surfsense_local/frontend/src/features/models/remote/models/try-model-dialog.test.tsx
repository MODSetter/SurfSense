import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import type { ConnectionModel } from "./api"
import { TryModelDialog } from "./try-model-dialog"

afterEach(cleanup)

const FABLE: ConnectionModel = {
  connection_id: 3,
  connection_label: "Claude plan",
  name: "claude-fable-5-1",
  types: ["text_gen"],
  capability_source: "catalog",
  selectable_for: ["text_gen"],
  reads_images: true,
}

function open(plan: boolean) {
  render(
    <TryModelDialog
      open
      modelType="text_gen"
      model={FABLE}
      unlisted={false}
      plan={plan}
      onOpenChange={vi.fn()}
      onOpenChangeComplete={vi.fn()}
    />
  )
}

describe("what testing a chat model costs", () => {
  it("counts toward a plan's limits, and costs no money, on a plan", async () => {
    open(true)

    const dialog = await screen.findByRole("dialog")
    expect(dialog.textContent).toContain("counts toward your plan’s limits")
    expect(dialog.textContent).not.toContain("may cost money")
  })

  it("may cost money on a server that bills per request", async () => {
    open(false)

    expect((await screen.findByRole("dialog")).textContent).toContain(
      "may cost money"
    )
  })
})
