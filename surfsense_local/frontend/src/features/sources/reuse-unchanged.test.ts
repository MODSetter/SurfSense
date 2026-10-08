import { describe, expect, it } from "vitest"

import type { WorkspaceDocument } from "./api"
import { reuseUnchanged } from "./reuse-unchanged"

function source(id: number, status: WorkspaceDocument["status"] = "ready") {
  return {
    id,
    title: `${id}.pdf`,
    document_type: "FILE" as const,
    mime_type: "application/pdf",
    status,
    error_message: null,
    created_at: "2026-10-07T00:00:00Z",
    updated_at: "2026-10-07T00:00:00Z",
    folder_id: null,
  }
}

describe("reuseUnchanged", () => {
  it("keeps the current list when a re-read changed nothing", () => {
    const current = [source(1), source(2)]

    expect(reuseUnchanged(current, [source(1), source(2)])).toBe(current)
  })

  it("keeps each unchanged source's object and takes the changed one", () => {
    const current = [source(1, "processing"), source(2)]
    const next = [source(1), source(2)]

    const merged = reuseUnchanged(current, next)

    expect(merged).toEqual(next)
    expect(merged[0]).toBe(next[0])
    expect(merged[1]).toBe(current[1])
  })

  it("follows the re-read's order, additions and removals", () => {
    const current = [source(1), source(2), source(3)]
    const added = source(4)

    const merged = reuseUnchanged(current, [added, source(3), source(1)])

    expect(merged).toEqual([added, current[2], current[0]])
    expect(merged[1]).toBe(current[2])
    expect(merged[2]).toBe(current[0])
  })

  it("counts a field only one side has as a change", () => {
    const current = [source(1)]
    // An API without folders sends no folder_id.
    const withoutFolder: WorkspaceDocument = source(1)
    delete withoutFolder.folder_id

    expect(reuseUnchanged(current, [withoutFolder])[0]).toBe(withoutFolder)
  })
})
