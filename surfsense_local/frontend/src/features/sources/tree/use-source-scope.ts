import { useEffect, useMemo, useState } from "react"

import { useStableCallback } from "@/hooks/use-stable-callback"

import type { WorkspaceDocument } from "../api"
import { readRememberedTicks, rememberTicks } from "./remembered-ticks"
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
  workspaceId: number,
  index: SourceIndex,
  documents: WorkspaceDocument[]
) {
  // The ticks belong to the workspace they were read for, so a switch reloads
  // them. A chat's own ticks take their place while that chat is open: those
  // are the chat's, not the workspace's to remember.
  const [held, setHeld] = useState(() => ({
    workspaceId,
    marks: readRememberedTicks(workspaceId),
    remembered: true,
  }))
  if (held.workspaceId !== workspaceId) {
    setHeld({
      workspaceId,
      marks: readRememberedTicks(workspaceId),
      remembered: true,
    })
  }
  const marks = held.marks
  const setMarks = useStableCallback(
    (next: ScopeMarks | ((current: ScopeMarks) => ScopeMarks)) =>
      setHeld((current) => ({
        ...current,
        marks: typeof next === "function" ? next(current.marks) : next,
      }))
  )
  // Counts the user's own ticks, not a scope put on screen for a chat, so a
  // chat can tell its ticks from the ones it was opened with.
  const [edits, setEdits] = useState(0)

  useEffect(() => {
    if (held.remembered) rememberTicks(held.workspaceId, held.marks)
  }, [held])

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
  // What a chat stored: not one of the user's edits, and the chat's from here.
  const setScope = useStableCallback((scope: SourceScope) =>
    setHeld((current) => ({
      workspaceId: current.workspaceId,
      marks: marksOf(scope, index),
      remembered: false,
    }))
  )
  // The ticks on screen are a chat's from here: they stay, and are no longer
  // the workspace's to remember.
  const keepForChat = useStableCallback(() =>
    setHeld((current) =>
      current.remembered ? { ...current, remembered: false } : current
    )
  )
  // The chat the ticks on screen were kept for never opened: they are the
  // workspace's again. Written at once, since another chat's ticks may take
  // the screen in the same update.
  const rememberShown = useStableCallback(() => {
    rememberTicks(held.workspaceId, held.marks)
    setHeld((current) =>
      current.remembered ? current : { ...current, remembered: true }
    )
  })
  // The workspace's own ticks, which a new chat starts from.
  const showRemembered = useStableCallback(() =>
    setHeld((current) => ({
      workspaceId: current.workspaceId,
      marks: readRememberedTicks(current.workspaceId),
      remembered: true,
    }))
  )

  return {
    ...derived,
    edits,
    setDocumentIncluded,
    setFolderIncluded,
    toggleAllIncluded,
    setScope,
    keepForChat,
    rememberShown,
    showRemembered,
  }
}
