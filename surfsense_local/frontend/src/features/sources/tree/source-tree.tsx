import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react"

import { getFileViewer } from "@/features/file-viewers/registry"
import { useStableCallback } from "@/hooks/use-stable-callback"
import { intl } from "@/i18n/intl"

import type { WorkspaceDocument } from "../api"
import { DocumentRow } from "./document-row"
import { FolderRow } from "./folder-row"
import type { SourceFolder } from "./folders-api"
import type { Tick } from "./scope-state"
import { TOP, type FolderKey, type SourceIndex } from "./source-index"
import type { MoveTarget } from "./move-to-dialog"
import type { TreeRowEvents } from "./tree-item"
import { documentKey, visibleRows, type TreeRow } from "./visible-rows"

export type DocumentRowActions = {
  onOpen: (documentId: number) => void
  onPreview?: (documentId: number) => void
  onReveal: (documentId: number) => void
  onRetry: (documentId: number) => void
  onCancel: (documentId: number) => void
  onDelete: (document: WorkspaceDocument) => void
  onRename?: (document: WorkspaceDocument) => void
  onEditNote?: (documentId: number) => void
  onSelectionChange: (documentId: number, selected: boolean) => void
}

/** What a folder row asks of its owner; absent, the tree has no folder actions. */
export type FolderRowActions = {
  onTickChange: (folderId: number, included: boolean) => void
  onNewFolder: (parent: FolderKey) => void
  onRename: (folder: SourceFolder) => void
  onDelete: (folder: SourceFolder) => void
  onMoveRequest: (target: MoveTarget) => void
}

// Memoized, and every row too: a row renders again only when its own values
// change, so ticking one source or opening a preview touches that row alone.
export const SourceTree = memo(function SourceTree({
  index,
  expanded,
  onExpandedChange,
  filter,
  selectedDocumentIds,
  folderTicks,
  highlightedDocumentId,
  isDeleting,
  documentActions,
  folderActions,
  dropFolder,
  takesFiles,
  labelledBy,
}: {
  index: SourceIndex
  expanded: ReadonlySet<number>
  onExpandedChange: (folderId: number, expanded: boolean) => void
  filter: string
  selectedDocumentIds: ReadonlySet<number>
  folderTicks: ReadonlyMap<number, Tick>
  highlightedDocumentId: number | null
  isDeleting: boolean
  documentActions: DocumentRowActions
  folderActions?: FolderRowActions
  // The folder a drag over the panel would file into, lit up.
  dropFolder: FolderKey | undefined
  // Whether rows take files dropped from the desktop.
  takesFiles: boolean
  labelledBy: string
}) {
  const rows = useMemo(
    () => visibleRows(index, expanded, filter),
    [index, expanded, filter]
  )
  const rowElements = useRef(new Map<string, HTMLLIElement>())
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const focusable =
    rows.find((row) => row.key === activeKey)?.key ?? rows[0]?.key
  const movable = folderActions !== undefined
  // Absent folders, there is nowhere to move a source to.
  const onMoveRequest =
    index.folders.size > 0 ? folderActions?.onMoveRequest : undefined

  useEffect(() => {
    if (highlightedDocumentId === null) return
    rowElements.current
      .get(documentKey(highlightedDocumentId))
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [highlightedDocumentId])

  const focusRow = (row: TreeRow | undefined) => {
    if (!row) return
    setActiveKey(row.key)
    rowElements.current.get(row.key)?.focus()
  }

  const tickRow = (row: TreeRow) => {
    if (row.kind === "folder") {
      folderActions?.onTickChange(
        row.folder.id,
        folderTicks.get(row.folder.id) !== "checked"
      )
    } else if (row.document.status === "ready") {
      documentActions.onSelectionChange(
        row.document.id,
        !selectedDocumentIds.has(row.document.id)
      )
    }
  }

  const activate = (row: TreeRow) => {
    if (row.kind === "folder") {
      onExpandedChange(row.folder.id, !row.expanded)
      return
    }
    const { document } = row
    if (getFileViewer(document.mime_type) !== null) {
      documentActions.onPreview?.(document.id)
    } else if (
      document.status === "ready" &&
      document.document_type === "FILE"
    ) {
      documentActions.onOpen(document.id)
    }
  }

  const onRowKeyDown = (event: KeyboardEvent<HTMLLIElement>, at: number) => {
    // Keys inside a row's own controls are theirs.
    if (event.target !== event.currentTarget) return
    const row = rows[at]
    const handled = () => event.preventDefault()
    switch (event.key) {
      case "ArrowDown":
        handled()
        focusRow(rows[at + 1])
        break
      case "ArrowUp":
        handled()
        focusRow(rows[at - 1])
        break
      case "Home":
        handled()
        focusRow(rows[0])
        break
      case "End":
        handled()
        focusRow(rows[rows.length - 1])
        break
      case "ArrowRight":
        handled()
        if (row.kind === "folder" && row.hasChildren) {
          if (!row.expanded) onExpandedChange(row.folder.id, true)
          else focusRow(rows[at + 1])
        }
        break
      case "ArrowLeft":
        handled()
        if (row.kind === "folder" && row.expanded) {
          onExpandedChange(row.folder.id, false)
        } else if (row.parent !== TOP) {
          const parentKey = row.parent
          focusRow(
            rows.find(
              (candidate) =>
                candidate.kind === "folder" && candidate.folder.id === parentKey
            )
          )
        }
        break
      case " ":
        handled()
        tickRow(row)
        break
      case "Enter":
        handled()
        activate(row)
        break
      case "F2":
        handled()
        if (row.kind === "folder") folderActions?.onRename(row.folder)
        else documentActions.onRename?.(row.document)
        break
      case "Delete":
        handled()
        if (row.kind === "folder") folderActions?.onDelete(row.folder)
        else if (row.document.status !== "processing" && !isDeleting) {
          documentActions.onDelete(row.document)
        }
        break
    }
  }

  // One for every row, reading the rows as they are when the key is pressed.
  const keyDownOnRow = useStableCallback(
    (event: KeyboardEvent<HTMLLIElement>, key: string) => {
      const at = rows.findIndex((row) => row.key === key)
      if (at !== -1) onRowKeyDown(event, at)
    }
  )
  const registerRow = useCallback((key: string, node: HTMLLIElement) => {
    rowElements.current.set(key, node)
    return () => {
      if (rowElements.current.get(key) === node) rowElements.current.delete(key)
    }
  }, [])
  const rowEvents = useMemo<TreeRowEvents>(
    () => ({
      register: registerRow,
      focused: setActiveKey,
      keyDown: keyDownOnRow,
    }),
    [registerRow, keyDownOnRow]
  )

  if (rows.length === 0) {
    return filter.trim() ? (
      <p className="px-2 py-3 text-sm text-muted-foreground">
        {intl.formatMessage(
          {
            id: "sources_tree_filter_empty",
            defaultMessage: "No sources match “{filter}”",
          },
          { filter: filter.trim() }
        )}
      </p>
    ) : null
  }

  return (
    <ul
      role="tree"
      aria-labelledby={labelledBy}
      className="flex list-none flex-col gap-1"
    >
      {rows.map((row) =>
        row.kind === "folder" ? (
          <FolderRow
            key={row.key}
            rowKey={row.key}
            level={row.level}
            setSize={row.setSize}
            posInSet={row.posInSet}
            tabbable={row.key === focusable}
            folder={row.folder}
            parent={row.parent}
            expanded={row.expanded}
            hasChildren={row.hasChildren}
            tick={folderTicks.get(row.folder.id) ?? "unchecked"}
            dropping={dropFolder === row.folder.id}
            movable={movable}
            takesFiles={takesFiles}
            events={rowEvents}
            onExpandedChange={onExpandedChange}
            actions={folderActions}
          />
        ) : (
          <DocumentRow
            key={row.key}
            rowKey={row.key}
            level={row.level}
            setSize={row.setSize}
            posInSet={row.posInSet}
            tabbable={row.key === focusable}
            document={row.document}
            parent={row.parent}
            selected={selectedDocumentIds.has(row.document.id)}
            highlighted={highlightedDocumentId === row.document.id}
            isDeleting={isDeleting}
            movable={movable}
            takesFiles={takesFiles}
            events={rowEvents}
            actions={documentActions}
            onMoveRequest={onMoveRequest}
          />
        )
      )}
    </ul>
  )
})
