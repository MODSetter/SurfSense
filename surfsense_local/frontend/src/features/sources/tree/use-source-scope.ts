import { useMemo, useState } from "react"

import { useStableCallback } from "@/hooks/use-stable-callback"

import type { WorkspaceDocument } from "../api"
import {
  everySource,
  isDocumentIncluded,
  markIncluded,
  scopeOf,
  ticksOf,
  type ScopeMarks,
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
    (documentId: number, included: boolean) =>
      setMarks((current) =>
        markIncluded(
          current,
          index,
          { kind: "document", id: documentId },
          included
        )
      )
  )
  const setFolderIncluded = useStableCallback(
    (folderId: number, included: boolean) =>
      setMarks((current) =>
        markIncluded(current, index, { kind: "folder", id: folderId }, included)
      )
  )
  const toggleAllIncluded = useStableCallback(() =>
    setMarks(everySource(derived.ticks.get(TOP_TICK) !== "checked"))
  )

  return {
    ...derived,
    setDocumentIncluded,
    setFolderIncluded,
    toggleAllIncluded,
  }
}
