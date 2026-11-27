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

  it("leaves a chat's ticks out of what the workspace remembers", () => {
    const { result, unmount } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))
    // A chat is opened: its stored ticks, then one the user makes in it.
    act(() =>
      result.current.setScope({
        all: false,
        folder_ids: [2],
        excluded_folder_ids: [],
        document_ids: [],
        excluded_document_ids: [],
      })
    )
    expect(result.current.includedDocumentIds).toEqual([20])
    act(() => result.current.setDocumentIncluded(20, false))
    unmount()

    expect(scopeFor(1).result.current.includedDocumentIds).toEqual([10])
  })

  it("leaves the ticks on screen to the chat they opened", () => {
    const { result, unmount } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))
    act(() => result.current.keepForChat())
    expect(result.current.includedDocumentIds).toEqual([10])
    act(() => result.current.setDocumentIncluded(20, true))
    unmount()

    expect(scopeFor(1).result.current.includedDocumentIds).toEqual([10])
  })

  it("remembers again the ticks kept for a chat that never opened", () => {
    const { result, unmount } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))
    act(() => result.current.keepForChat())
    act(() => result.current.setDocumentIncluded(20, true))
    act(() => result.current.rememberShown())
    expect(result.current.includedDocumentIds).toEqual([10, 20])
    unmount()

    expect(scopeFor(1).result.current.includedDocumentIds).toEqual([10, 20])
  })

  it("remembers them even when another chat's ticks take the screen at once", () => {
    const { result, unmount } = scopeFor(1)
    act(() => result.current.keepForChat())
    act(() => result.current.setDocumentIncluded(20, true))
    act(() => {
      result.current.rememberShown()
      result.current.setScope({
        all: false,
        folder_ids: [],
        excluded_folder_ids: [],
        document_ids: [10],
        excluded_document_ids: [],
      })
    })
    expect(result.current.includedDocumentIds).toEqual([10])
    unmount()

    expect(scopeFor(1).result.current.includedDocumentIds).toEqual([20])
  })

  it("shows the workspace's ticks again for a new chat, and remembers its ticks", () => {
    const { result, unmount } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))
    act(() =>
      result.current.setScope({
        all: true,
        folder_ids: [],
        excluded_folder_ids: [],
        document_ids: [],
        excluded_document_ids: [],
      })
    )
    expect(result.current.includedDocumentIds).toEqual([10, 20])

    act(() => result.current.showRemembered())
    expect(result.current.includedDocumentIds).toEqual([10])
    act(() => result.current.setDocumentIncluded(20, true))
    unmount()

    expect(scopeFor(1).result.current.includedDocumentIds).toEqual([10, 20])
  })

  it("counts the user's ticks, not a chat's ticks put on screen", () => {
    const { result } = scopeFor(1)
    act(() => result.current.setDocumentIncluded(10, true))
    expect(result.current.edits).toBe(1)
    act(() => result.current.keepForChat())
    act(() => result.current.showRemembered())
    expect(result.current.edits).toBe(1)
  })

  it("starts with none ticked when the saved ticks are unreadable", () => {
    localStorage.setItem("surfsense:source-ticks:v1", "{not json")

    const { result } = scopeFor(1)

    expect(result.current.includedDocumentIds).toEqual([])
  })
})
