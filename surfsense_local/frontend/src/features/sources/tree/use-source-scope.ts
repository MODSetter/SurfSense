import { useMemo, useState } from "react"

import { useStableCallback } from "@/hooks/use-stable-callback"

import type { WorkspaceDocument } from "../api"
import {
  everySource,
  isDocumentIncluded,
  markIncluded,
  marksOf,
  scopeOf,
  ticksOf,
  type ScopeMarks,
  type SourceScope,
} from "./scope-state"
import type { SourceIndex } from "./source-index"

// The top level's key in `ticks`.
export const TOP_TICK = -1

/** The ticks in the sources panel, and what chat and Studio send from them. */
export function useSourceScope(
  index: SourceIndex,
  documents: WorkspaceDocument[]
) {
  // Every source by default, as the flat list ticked every ready row.
  const [marks, setMarks] = useState<ScopeMarks>(() => everySource(true))
  // Counts the user's own ticks, not a scope put on screen for a chat, so a
  // chat can tell its ticks from the ones it was opened with.
  const [edits, setEdits] = useState(0)

  const derived = useMemo(() => {
    const ticks = ticksOf(marks, index)
    const includedDocumentIds = documents.flatMap((document) =>
      document.status === "ready" &&
      isDocumentIncluded(marks, index, document.id)
        ? [document.id]
        : []
    )
    return { ticks, includedDocumentIds, scope: scopeOf(marks, index) }
  }, [documents, index, marks])

  // Stable: they reach every row of the memoized tree.
  const setDocumentIncluded = useStableCallback(
    (documentId: number, included: boolean) => {
      setMarks((current) =>
        markIncluded(
          current,
          index,
          { kind: "document", id: documentId },
          included
        )
      )
      setEdits((count) => count + 1)
    }
  )
  const setFolderIncluded = useStableCallback(
    (folderId: number, included: boolean) => {
      setMarks((current) =>
        markIncluded(current, index, { kind: "folder", id: folderId }, included)
      )
      setEdits((count) => count + 1)
    }
  )
  const toggleAllIncluded = useStableCallback(() => {
    setMarks(everySource(derived.ticks.get(TOP_TICK) !== "checked"))
    setEdits((count) => count + 1)
  })
  // What a chat stored, or the draft a new chat kept: not one of the user's edits.
  const setScope = useStableCallback((scope: SourceScope) =>
    setMarks(marksOf(scope))
  )

  return {
    ...derived,
    edits,
    setDocumentIncluded,
    setFolderIncluded,
    toggleAllIncluded,
    setScope,
  }
}
