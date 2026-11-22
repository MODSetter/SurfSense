import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { WorkspaceDocument } from "./api"
import { SourceChecklist } from "./source-checklist"

const document = (id: number, title: string): WorkspaceDocument => ({
  id,
  title,
  document_type: "FILE",
  mime_type: "application/pdf",
  status: "ready",
  error_message: null,
  created_at: "2026-11-01T09:00:00Z",
  updated_at: "2026-11-01T09:00:00Z",
})

const DOCUMENTS = [
  document(3, "Security policy.pdf"),
  document(4, "Backups.pdf"),
]

function Ticking({ disabled }: { disabled?: boolean }) {
  const [ticked, setTicked] = useState(new Set([3]))
  return (
    <SourceChecklist
      documents={DOCUMENTS}
      isChecked={(id) => ticked.has(id)}
      onToggle={(id, checked) =>
        setTicked((current) => {
          const next = new Set(current)
          if (checked) next.add(id)
          else next.delete(id)
          return next
        })
      }
      disabled={disabled}
    />
  )
}

const checked = (name: string) =>
  screen.getByRole("checkbox", { name }).getAttribute("aria-checked")

afterEach(cleanup)

describe("source checklist", () => {
  it("ticks a source by its box or its name", async () => {
    const user = userEvent.setup()
    render(<Ticking />)

    expect(checked("Security policy.pdf")).toBe("true")
    expect(checked("Backups.pdf")).toBe("false")
    await user.click(screen.getByRole("checkbox", { name: "Backups.pdf" }))
    await user.click(screen.getByText("Security policy.pdf"))

    expect(checked("Backups.pdf")).toBe("true")
    expect(checked("Security policy.pdf")).toBe("false")
  })

  it("asks for each change with the tick it should take", async () => {
    const onToggle = vi.fn()
    const user = userEvent.setup()
    render(
      <SourceChecklist
        documents={DOCUMENTS}
        isChecked={(id) => id === 3}
        onToggle={onToggle}
      />
    )

    await user.click(screen.getByText("Security policy.pdf"))
    await user.click(screen.getByText("Backups.pdf"))

    expect(onToggle.mock.calls).toEqual([
      [3, false],
      [4, true],
    ])
  })

  it("holds every tick while disabled", async () => {
    const user = userEvent.setup()
    render(<Ticking disabled />)

    await user.click(screen.getByRole("checkbox", { name: "Backups.pdf" }))

    expect(checked("Backups.pdf")).toBe("false")
  })
})
