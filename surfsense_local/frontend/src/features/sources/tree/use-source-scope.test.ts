import { afterEach, describe, expect, it } from "vitest"
import { act, renderHook } from "@testing-library/react"

import type { WorkspaceDocument } from "../api"
import { indexSources } from "./source-index"
import { useSourceScope } from "./use-source-scope"

function source(id: number, folderId: number | null): WorkspaceDocument {
  return {
    id,
    title: `source ${id}`,
    document_type: "FILE",
    mime_type: null,
    status: "ready",
    error_message: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    folder_id: folderId,
  }
}

// The Library (1) holds source 10 and Research (2), which holds source 20.
const DOCUMENTS = [source(10, 1), source(20, 2)]
const index = indexSources(
  [
    { id: 1, parent_id: null, name: "Library" },
    { id: 2, parent_id: 1, name: "Research" },
  ],
  DOCUMENTS
)

function scopeFor(workspaceId: number) {
  return renderHook(
    ({ workspaceId }) => useSourceScope(workspaceId, index, DOCUMENTS),
    { initialProps: { workspaceId } }
  )
}

afterEach(() => localStorage.clear())

describe("useSourceScope", () => {
  it("starts with no source ticked", () => {
    const { result } = scopeFor(1)

    expect(result.current.includedDocumentIds).toEqual([])
    expect(result.current.scope.all).toBe(false)
  })

  it("keeps a workspace's ticks when the app opens again", () => {
    const first = scopeFor(1)
    act(() => first.result.current.setFolderIncluded(2, true))
    first.unmount()

    const reopened = scopeFor(1)

    expect(reopened.result.current.includedDocumentIds).toEqual([20])
    expect(reopened.result.current.scope.folder_ids).toEqual([2])
  })

  it("keeps each workspace's ticks to itself", () => {
    const { result, rerender } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))

    rerender({ workspaceId: 2 })
    expect(result.current.includedDocumentIds).toEqual([])

    rerender({ workspaceId: 1 })
    expect(result.current.includedDocumentIds).toEqual([10])
  })

  it("starts with none ticked when the saved ticks are unreadable", () => {
    localStorage.setItem("surfsense:source-ticks:v1", "{not json")

    const { result } = scopeFor(1)

    expect(result.current.includedDocumentIds).toEqual([])
  })
})
