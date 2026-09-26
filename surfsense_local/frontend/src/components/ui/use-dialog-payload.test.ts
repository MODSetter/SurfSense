import { renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useDialogOpening, useDialogPayload } from "./use-dialog-payload"

describe("useDialogPayload", () => {
  it("keeps the last payload after the dialog closes", () => {
    const { result, rerender } = renderHook(
      ({ value }: { value: string | null }) => useDialogPayload(value),
      { initialProps: { value: "Report.pdf" as string | null } }
    )

    rerender({ value: null })

    expect(result.current.payload).toBe("Report.pdf")
  })

  it("counts a new opening on reopen, even with the same payload", () => {
    const item = { id: 1 }
    const { result, rerender } = renderHook(
      ({ value }: { value: { id: number } | null }) => useDialogPayload(value),
      { initialProps: { value: item as { id: number } | null } }
    )
    const first = result.current.opening

    rerender({ value: null })
    expect(result.current.opening).toBe(first)
    rerender({ value: item })

    expect(result.current.opening).not.toBe(first)
  })
})

describe("useDialogOpening", () => {
  it("changes when the dialog opens, not when it closes", () => {
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) => useDialogOpening(open),
      { initialProps: { open: false } }
    )

    rerender({ open: true })
    const opened = result.current
    rerender({ open: false })

    expect(result.current).toBe(opened)
    rerender({ open: true })
    expect(result.current).not.toBe(opened)
  })
})
