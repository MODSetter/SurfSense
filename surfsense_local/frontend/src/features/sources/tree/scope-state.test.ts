import { describe, expect, it } from "vitest"

import type { WorkspaceDocument } from "../api"
import {
  everySource,
  isDocumentIncluded,
  markIncluded,
  scopeOf,
  ticksOf,
} from "./scope-state"
import { indexSources } from "./source-index"

function source(id: number, folderId: number): WorkspaceDocument {
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

// Library (1) holds Research (2), which holds 2024 (3); one source in each.
const index = indexSources(
  [
    { id: 1, parent_id: null, name: "Library" },
    { id: 2, parent_id: 1, name: "Research" },
    { id: 3, parent_id: 2, name: "2024" },
  ],
  [source(10, 1), source(20, 2), source(30, 3)]
)

describe("source scope ticks", () => {
  it("sends every source as all, whatever is loaded", () => {
    expect(scopeOf(everySource(true), index)).toEqual({
      all: true,
      folder_ids: [],
      excluded_folder_ids: [],
      document_ids: [],
      excluded_document_ids: [],
    })
  })

  it("ticks everything under a folder, as one folder id", () => {
    const marks = markIncluded(
      everySource(false),
      index,
      { kind: "folder", id: 2 },
      true
    )

    expect(isDocumentIncluded(marks, index, 30)).toBe(true)
    expect(isDocumentIncluded(marks, index, 10)).toBe(false)
    expect(scopeOf(marks, index)).toMatchObject({
      all: false,
      folder_ids: [2],
      excluded_folder_ids: [],
    })
    expect(ticksOf(marks, index).get(2)).toBe("checked")
    expect(ticksOf(marks, index).get(-1)).toBe("mixed")
  })

  it("shows a folder with one unticked source as mixed", () => {
    const marks = markIncluded(
      everySource(true),
      index,
      { kind: "document", id: 30 },
      false
    )

    expect(ticksOf(marks, index).get(3)).toBe("unchecked")
    expect(ticksOf(marks, index).get(2)).toBe("mixed")
    expect(scopeOf(marks, index)).toMatchObject({
      all: true,
      excluded_document_ids: [30],
    })
  })

  it("excludes a subfolder whole, and keeps a source ticked again inside it", () => {
    const unticked = markIncluded(
      everySource(true),
      index,
      { kind: "folder", id: 2 },
      false
    )
    expect(scopeOf(unticked, index)).toMatchObject({
      excluded_folder_ids: [2],
    })

    const retick = markIncluded(
      unticked,
      index,
      { kind: "folder", id: 3 },
      true
    )
    // The server removes excluded folders after adding ticked ones, so the
    // parent's own sources are excluded one by one instead.
    expect(scopeOf(retick, index)).toEqual({
      all: true,
      folder_ids: [],
      excluded_folder_ids: [],
      document_ids: [],
      excluded_document_ids: [20],
    })
    expect(isDocumentIncluded(retick, index, 30)).toBe(true)
  })

  it("keeps an unticked folder excluded whole when one source inside it is ticked", () => {
    const unticked = markIncluded(
      everySource(true),
      index,
      { kind: "folder", id: 2 },
      false
    )
    const one = markIncluded(
      unticked,
      index,
      { kind: "document", id: 30 },
      true
    )

    // Excluding the folder keeps a file added to it later out, and the list
    // of excluded rows never grows with the folder.
    expect(scopeOf(one, index)).toEqual({
      all: true,
      folder_ids: [],
      excluded_folder_ids: [2],
      document_ids: [30],
      excluded_document_ids: [],
    })
  })

  it("forgets the ticks under a folder once the folder is ticked", () => {
    const one = markIncluded(
      everySource(false),
      index,
      { kind: "document", id: 30 },
      true
    )
    const whole = markIncluded(one, index, { kind: "folder", id: 2 }, true)

    expect(whole.documents.size).toBe(0)
    expect(scopeOf(whole, index).document_ids).toEqual([])
  })
})
