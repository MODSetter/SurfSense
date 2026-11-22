import { afterEach, describe, expect, it } from "vitest"
import { act, renderHook } from "@testing-library/react"

import { EXPANDED_FOLDERS_KEY } from "./expanded-folders"
import { indexSources, type SourceIndex } from "./source-index"
import { useExpandedFolders } from "./use-expanded-folders"

// The Library (1) holds Research (2) and Drafts (3).
const LIBRARY = { id: 1, parent_id: null, name: "Library" }
const RESEARCH = { id: 2, parent_id: 1, name: "Research" }
const DRAFTS = { id: 3, parent_id: 1, name: "Drafts" }
const index = indexSources([LIBRARY, RESEARCH, DRAFTS], [])

function expandedFor(workspaceId: number | null, given: SourceIndex = index) {
  return renderHook(
    ({ workspaceId, index }) => useExpandedFolders(workspaceId, index),
    { initialProps: { workspaceId, index: given } }
  )
}

afterEach(() => localStorage.clear())

describe("useExpandedFolders", () => {
  it("starts with every folder closed", () => {
    const { result } = expandedFor(1)

    expect([...result.current.expanded]).toEqual([])
  })

  it("keeps a workspace's open folders when the app opens again", () => {
    const first = expandedFor(1)
    act(() => first.result.current.setFolderExpanded(2, true))
    act(() => first.result.current.setFolderExpanded(3, true))
    act(() => first.result.current.setFolderExpanded(3, false))
    first.unmount()

    const reopened = expandedFor(1)

    expect([...reopened.result.current.expanded]).toEqual([2])
  })

  it("keeps each workspace's open folders to itself", () => {
    const { result, rerender } = expandedFor(1)
    act(() => result.current.setFolderExpanded(2, true))

    rerender({ workspaceId: 2, index })
    expect([...result.current.expanded]).toEqual([])

    rerender({ workspaceId: 1, index })
    expect([...result.current.expanded]).toEqual([2])
  })

  it("forgets a folder the listing no longer has", () => {
    const { result, rerender, unmount } = expandedFor(1)
    act(() => result.current.setFolderExpanded(2, true))
    act(() => result.current.setFolderExpanded(3, true))

    rerender({ workspaceId: 1, index: indexSources([LIBRARY, DRAFTS], []) })
    expect([...result.current.expanded]).toEqual([3])
    unmount()

    // A folder made later with the deleted one's id starts closed.
    const reopened = expandedFor(1)
    expect([...reopened.result.current.expanded]).toEqual([3])
  })

  it("keeps the open folders while the folders are still loading", () => {
    const first = expandedFor(1)
    act(() => first.result.current.setFolderExpanded(2, true))
    first.unmount()

    const { result, rerender } = expandedFor(1, indexSources([], []))
    expect([...result.current.expanded]).toEqual([2])

    rerender({ workspaceId: 1, index })
    expect([...result.current.expanded]).toEqual([2])
  })

  it("keeps nothing without a workspace", () => {
    const first = expandedFor(null)
    act(() => first.result.current.setFolderExpanded(2, true))
    expect([...first.result.current.expanded]).toEqual([2])
    first.unmount()

    expect(localStorage.getItem(EXPANDED_FOLDERS_KEY)).toBeNull()
  })

  it("starts with every folder closed when the saved folders are unreadable", () => {
    localStorage.setItem(EXPANDED_FOLDERS_KEY, "{not json")

    const { result } = expandedFor(1)

    expect([...result.current.expanded]).toEqual([])
  })
})
