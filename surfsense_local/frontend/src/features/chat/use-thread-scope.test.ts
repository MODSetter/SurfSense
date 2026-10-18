import { afterEach, describe, expect, it } from "vitest"

import {
  clearDraftScope,
  draftScopeSnapshot,
  readDraftScope,
} from "./use-thread-scope"

const key = "surfsense:draft-scope:1:v1"
const draft = {
  all: true,
  folder_ids: [],
  excluded_folder_ids: [2],
  document_ids: [],
  excluded_document_ids: [],
}

afterEach(() => localStorage.clear())

describe("a new chat's draft", () => {
  it("reads only a whole draft back", () => {
    expect(readDraftScope(1)).toBeNull()
    localStorage.setItem(key, JSON.stringify(draft))
    expect(readDraftScope(1)).toEqual(draft)
    localStorage.setItem(key, JSON.stringify({ all: true, folder_ids: ["2"] }))
    expect(readDraftScope(1)).toBeNull()
    localStorage.setItem(key, "not json")
    expect(readDraftScope(1)).toBeNull()
  })

  it("is spent once its thread is opened, unless a newer chat wrote one since", () => {
    localStorage.setItem(key, JSON.stringify(draft))
    const opening = draftScopeSnapshot(1)
    // The user started another chat and ticked while the thread was opening.
    localStorage.setItem(key, JSON.stringify({ ...draft, excluded_folder_ids: [3] }))
    clearDraftScope(1, opening)
    expect(readDraftScope(1)).toEqual({ ...draft, excluded_folder_ids: [3] })
    // Unchanged since the opening started, the draft goes.
    clearDraftScope(1, draftScopeSnapshot(1))
    expect(readDraftScope(1)).toBeNull()
    // Without a snapshot the draft goes whatever it holds.
    localStorage.setItem(key, JSON.stringify(draft))
    clearDraftScope(1)
    expect(readDraftScope(1)).toBeNull()
  })
})
