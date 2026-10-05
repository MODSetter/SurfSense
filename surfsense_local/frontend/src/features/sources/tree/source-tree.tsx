import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
} from "react"

import { getFileViewer } from "@/features/file-viewers/registry"
import { intl } from "@/i18n/intl"

import type { WorkspaceDocument } from "../api"
import { DROP_FOLDER_ATTRIBUTE, carriesFiles } from "../use-file-drop"
import { DocumentRow } from "./document-row"
import { FolderRow } from "./folder-row"
import type { SourceFolder } from "./folders-api"
import type { Tick } from "./scope-state"
import {
  TOP,
  subtreeOf,
  type FolderKey,
  type SourceIndex,
} from "./source-index"
import {
  carriesSource,
  draggedSource,
  startSourceDrag,
  type DraggedSource,
} from "./tree-drag"
import type { TreeItemProps } from "./tree-item-props"
import type { MoveTarget } from "./move-to-dialog"
import { visibleRows, type TreeRow } from "./visible-rows"

// Each level indents by this much, past the first.
const INDENT_PX = 16

const ARIA_TICK = {
  checked: "true",
  unchecked: "false",
  mixed: "mixed",
} as const satisfies Record<Tick, "true" | "false" | "mixed">

function dropFolderOf(event: DragEvent): FolderKey {
  const target = event.target instanceof Element ? event.target : null
  const value = target
    ?.closest(`[${DROP_FOLDER_ATTRIBUTE}]`)
    ?.getAttribute(DROP_FOLDER_ATTRIBUTE)
  return value ? Number(value) : TOP
}

/** Whether moving this row into that folder changes anything and is allowed. */
function canDrop(index: SourceIndex, source: DraggedSource, to: FolderKey) {
  if (source.kind === "document") {
    return index.folderOfDocument.get(source.id) !== to
  }
  if (index.parentOf.get(source.id) === to) return false
  return to === TOP || !subtreeOf(index, source.id).has(to)
}

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
  onDrop: (source: DraggedSource, to: FolderKey) => void
}

export function SourceTree({
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
  labelledBy: string
}) {
  const rows = visibleRows(index, expanded, filter)
  const rowElements = useRef(new Map<string, HTMLLIElement>())
  const documentElements = useRef(new Map<number, HTMLLIElement>())
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<FolderKey | undefined>(undefined)
  const focusable =
    rows.find((row) => row.key === activeKey)?.key ?? rows[0]?.key

  useEffect(() => {
    if (highlightedDocumentId === null) return
    documentElements.current
      .get(highlightedDocumentId)
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

  const itemPropsOf = (row: TreeRow, at: number): TreeItemProps => {
    const holder = row.kind === "folder" ? row.folder.id : row.parent
    return {
      role: "treeitem",
      "aria-level": row.level,
      "aria-setsize": row.setSize,
      "aria-posinset": row.posInSet,
      "aria-expanded": row.kind === "folder" ? row.expanded : undefined,
      // The row has focus, not its checkbox, so the row says what Space ticks.
      "aria-checked":
        row.kind === "folder"
          ? ARIA_TICK[folderTicks.get(row.folder.id) ?? "unchecked"]
          : row.document.status === "ready"
            ? selectedDocumentIds.has(row.document.id)
            : undefined,
      "aria-label":
        row.kind === "folder" ? row.folder.name : row.document.title,
      tabIndex: row.key === focusable ? 0 : -1,
      style:
        row.level > 1
          ? { paddingInlineStart: 4 + (row.level - 1) * INDENT_PX }
          : undefined,
      ...(holder !== TOP ? { [DROP_FOLDER_ATTRIBUTE]: holder } : {}),
      draggable: folderActions !== undefined,
      onDragStart: folderActions
        ? (event) =>
            startSourceDrag(
              event,
              row.kind === "folder"
                ? { kind: "folder", id: row.folder.id }
                : { kind: "document", id: row.document.id }
            )
        : undefined,
      onFocus: (event) => {
        if (event.target === event.currentTarget) setActiveKey(row.key)
      },
      onKeyDown: (event) => onRowKeyDown(event, at),
    }
  }

  // Files are taken by the panel, which reads the same row marker; rows
  // moved inside the tree are taken here.
  const dragHandlers = folderActions
    ? {
        onDragOver: (event: DragEvent<HTMLUListElement>) => {
          const internal = carriesSource(event)
          if (!internal && !carriesFiles(event)) return
          if (internal) {
            event.preventDefault()
            event.dataTransfer.dropEffect = "move"
          }
          setDropTarget(dropFolderOf(event))
        },
        onDragLeave: (event: DragEvent<HTMLUListElement>) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node)) {
            setDropTarget(undefined)
          }
        },
        onDrop: (event: DragEvent<HTMLUListElement>) => {
          setDropTarget(undefined)
          const source = carriesSource(event) ? draggedSource(event) : null
          if (!source) return
          event.preventDefault()
          const to = dropFolderOf(event)
          if (canDrop(index, source, to)) folderActions.onDrop(source, to)
        },
        onDragEnd: () => setDropTarget(undefined),
      }
    : {}

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
      {...dragHandlers}
    >
      {rows.map((row, at) =>
        row.kind === "folder" ? (
          <FolderRow
            key={row.key}
            folder={row.folder}
            expanded={row.expanded}
            hasChildren={row.hasChildren}
            tick={folderTicks.get(row.folder.id) ?? "unchecked"}
            dropping={dropTarget === row.folder.id}
            rowRef={(node) => {
              if (node) rowElements.current.set(row.key, node)
              else rowElements.current.delete(row.key)
            }}
            itemProps={itemPropsOf(row, at)}
            onToggleExpanded={() =>
              onExpandedChange(row.folder.id, !row.expanded)
            }
            onTickChange={(included) =>
              folderActions?.onTickChange(row.folder.id, included)
            }
            onNewFolder={() => folderActions?.onNewFolder(row.folder.id)}
            onRename={() => folderActions?.onRename(row.folder)}
            onMove={() =>
              folderActions?.onMoveRequest({
                kind: "folder",
                id: row.folder.id,
                name: row.folder.name,
                from: row.parent,
              })
            }
            onDelete={() => folderActions?.onDelete(row.folder)}
          />
        ) : (
          <DocumentRow
            key={row.key}
            document={row.document}
            selected={selectedDocumentIds.has(row.document.id)}
            highlighted={highlightedDocumentId === row.document.id}
            rowRef={(node) => {
              if (node) {
                rowElements.current.set(row.key, node)
                documentElements.current.set(row.document.id, node)
              } else {
                rowElements.current.delete(row.key)
                documentElements.current.delete(row.document.id)
              }
            }}
            itemProps={itemPropsOf(row, at)}
            onOpen={() => documentActions.onOpen(row.document.id)}
            onPreview={() => documentActions.onPreview?.(row.document.id)}
            onReveal={() => documentActions.onReveal(row.document.id)}
            onRetry={() => documentActions.onRetry(row.document.id)}
            onCancel={() => documentActions.onCancel(row.document.id)}
            onDelete={() => documentActions.onDelete(row.document)}
            onRename={
              documentActions.onRename
                ? () => documentActions.onRename?.(row.document)
                : undefined
            }
            onEditNote={
              documentActions.onEditNote
                ? () => documentActions.onEditNote?.(row.document.id)
                : undefined
            }
            onMove={
              folderActions && index.folders.size > 0
                ? () =>
                    folderActions.onMoveRequest({
                      kind: "document",
                      id: row.document.id,
                      name: row.document.title,
                      from: row.parent,
                    })
                : undefined
            }
            isDeleting={isDeleting}
            onSelectedChange={(selected) =>
              documentActions.onSelectionChange(row.document.id, selected)
            }
          />
        )
      )}
    </ul>
  )
}
