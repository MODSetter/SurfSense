import { useMemo, useRef, useState } from "react"
import { FilePlus2Icon, SearchIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { AddSourcesMenu, type SourceUploads } from "./add-sources-menu"
import type { WorkspaceDocument } from "./api"
import type { UploadEntry } from "./folder-upload/upload-plan"
import {
  NoteEditorDialog,
  type NoteActions,
  type NoteTarget,
} from "./note-editor-dialog"
import { RenameSourceDialog } from "./rename-source-dialog"
import { SourceFilterField } from "./source-filter-field"
import {
  DeleteFolderDialog,
  type FolderDeleteTarget,
} from "./tree/delete-folder-dialog"
import {
  FolderNameDialog,
  type FolderNameTarget,
} from "./tree/folder-name-dialog"
import type { FolderActions } from "./tree/use-folders"
import { MoveToDialog, type MoveTarget } from "./tree/move-to-dialog"
import type { Tick } from "./tree/scope-state"
import {
  documentsUnder,
  folderIdFor,
  indexSources,
  type FolderKey,
  type SourceIndex,
} from "./tree/source-index"
import { SourceTree, type FolderRowActions } from "./tree/source-tree"
import type { DraggedSource } from "./tree/tree-drag"
import { TOP_TICK } from "./tree/use-source-scope"
import { useFileDrop } from "./use-file-drop"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

export function SourcesPanel({
  documents,
  index: givenIndex,
  selectedDocumentIds,
  folderTicks,
  highlightedDocumentId,
  isLoading,
  isDeleting,
  error,
  upload,
  onOpen,
  onPreview,
  onReveal,
  onRetry,
  onCancel,
  onDelete,
  onDeleteSelected,
  onSelectionChange,
  onFolderSelectionChange,
  onToggleAll,
  onDropFiles,
  onRename,
  folderActions,
  notes,
}: {
  documents: WorkspaceDocument[]
  // The sources in their folders; absent, the documents are one flat list.
  index?: SourceIndex
  selectedDocumentIds: number[]
  folderTicks?: ReadonlyMap<number, Tick>
  highlightedDocumentId: number | null
  isLoading: boolean
  isDeleting: boolean
  error: string | null
  // Absent, the panel offers no upload.
  upload?: SourceUploads
  onOpen: (documentId: number) => void
  onPreview?: (documentId: number) => void
  onReveal: (documentId: number) => void
  onRetry: (documentId: number) => void
  onCancel: (documentId: number) => void
  onDelete: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
  onFolderSelectionChange?: (folderId: number, selected: boolean) => void
  onToggleAll: () => void
  // Files dropped on the panel, and the folder row they fell on (null for
  // the top level). Absent, the panel takes no drop: the caller withholds it
  // while an upload runs, as it disables Add.
  onDropFiles?: (entries: UploadEntry[], folderId: number | null) => void
  // Absent, the panel offers no rename and no notes.
  onRename?: (documentId: number, title: string) => Promise<boolean>
  // Absent, the panel offers no folders to make, move or delete.
  folderActions?: FolderActions
  notes?: NoteActions
}) {
  const flatIndex = useMemo(() => indexSources([], documents), [documents])
  const index = givenIndex ?? flatIndex
  const drop = useFileDrop(onDropFiles)
  const [deleteTarget, setDeleteTarget] = useState<
    WorkspaceDocument | "selected" | null
  >(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<WorkspaceDocument | null>(
    null
  )
  const [renameOpen, setRenameOpen] = useState(false)
  const [noteTarget, setNoteTarget] = useState<NoteTarget | null>(null)
  const [noteOpen, setNoteOpen] = useState(false)
  const [folderNameTarget, setFolderNameTarget] =
    useState<FolderNameTarget | null>(null)
  const [folderNameOpen, setFolderNameOpen] = useState(false)
  const [moveTarget, setMoveTarget] = useState<MoveTarget | null>(null)
  const [moveOpen, setMoveOpen] = useState(false)
  const [folderDeleteTarget, setFolderDeleteTarget] =
    useState<FolderDeleteTarget | null>(null)
  const [folderDeleteOpen, setFolderDeleteOpen] = useState(false)
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(() => new Set())
  const [filter, setFilter] = useState("")
  const [filterOpen, setFilterOpen] = useState(false)
  // Focus goes to the search button once it mounts in the field's place.
  const refocusFilterButton = useRef(false)
  const closeFilter = (returnFocus: boolean) => {
    setFilter("")
    setFilterOpen(false)
    refocusFilterButton.current = returnFocus
  }
  const openNote = (documentId: number | null) => {
    setNoteTarget({ documentId })
    setNoteOpen(true)
  }
  const deleteCount =
    deleteTarget === "selected"
      ? selectedDocumentIds.length
      : deleteTarget
        ? 1
        : 0
  const hasFolders = index.folders.size > 0
  // Folders are made in the root folder, so an API without one offers none.
  const organizing = folderActions !== undefined && index.rootFolderId !== null
  const filterable = hasFolders || documents.length > 0

  const setFolderExpanded = (folderId: number, open: boolean) =>
    setExpanded((current) => {
      const next = new Set(current)
      if (open) next.add(folderId)
      else next.delete(folderId)
      return next
    })

  const moveInto = async (
    source: DraggedSource,
    to: FolderKey
  ): Promise<boolean> => {
    const folderId = folderIdFor(index, to)
    if (!folderActions || folderId === null) return false
    const moved =
      source.kind === "document"
        ? await folderActions.moveDocuments([source.id], folderId)
        : await folderActions.move(source.id, folderId)
    if (moved && to !== null) setFolderExpanded(to, true)
    return moved
  }

  const folderRowActions: FolderRowActions | undefined = organizing
    ? {
        onTickChange: (folderId, included) =>
          onFolderSelectionChange?.(folderId, included),
        onNewFolder: (parent) => {
          setFolderNameTarget({ kind: "create", parentId: parent })
          setFolderNameOpen(true)
        },
        onRename: (folder) => {
          setFolderNameTarget({
            kind: "rename",
            folderId: folder.id,
            name: folder.name,
          })
          setFolderNameOpen(true)
        },
        onDelete: (folder) => {
          // The server's count: it knows the filed outputs the tree never lists.
          void (
            folderActions?.summarize(folder.id) ?? Promise.resolve(null)
          ).then((summary) => {
            setFolderDeleteTarget({
              id: folder.id,
              name: folder.name,
              sources:
                summary?.sources ?? documentsUnder(index, folder.id).length,
              artifacts: summary?.artifacts ?? 0,
            })
            setFolderDeleteOpen(true)
          })
        },
        onMoveRequest: (target) => {
          setMoveTarget(target)
          setMoveOpen(true)
        },
        onDrop: (source, to) => void moveInto(source, to),
      }
    : undefined

  const selectedDocumentIdSet = new Set(selectedDocumentIds)
  const readyDocuments = documents.filter(
    (document) => document.status === "ready"
  )
  const readyCount = readyDocuments.length
  const selectedReadyCount = readyDocuments.filter((document) =>
    selectedDocumentIdSet.has(document.id)
  ).length
  const allSelected = folderTicks
    ? folderTicks.get(TOP_TICK) === "checked"
    : readyCount > 0 && selectedDocumentIds.length === readyCount
  const toggleAllLabel = allSelected
    ? intl.formatMessage({
        id: "sources_list_deselect_all_button",
        defaultMessage: "Deselect all",
      })
    : intl.formatMessage({
        id: "sources_list_select_all_button",
        defaultMessage: "Select all",
      })
  const listHeader = (
    <div className="mb-2 flex min-h-7 shrink-0 items-center gap-1">
      {/* Kept for screen readers while the filter covers it: the list is
      labelled by it. */}
      <h3
        id="all-sources"
        className={cn(
          "min-w-0 flex-1 truncate px-1 text-sm font-medium text-muted-foreground",
          filterOpen && "sr-only"
        )}
      >
        {intl.formatMessage({
          id: "sources_list_title",
          defaultMessage: "Sources",
        })}
      </h3>
      {filterOpen ? (
        <SourceFilterField
          value={filter}
          onChange={setFilter}
          onClose={closeFilter}
        />
      ) : null}
      {readyCount > 0 && !filterOpen ? (
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                size="xs"
                variant="ghost"
                // Held in place while hidden, so the header never shifts.
                className="text-muted-foreground tabular-nums opacity-0 transition-opacity duration-150 group-hover/sources:opacity-100 focus-visible:opacity-100"
                aria-label={toggleAllLabel}
                onClick={onToggleAll}
              >
                {intl.formatMessage(
                  {
                    id: "sources_list_selected_status",
                    defaultMessage: "{selected, number}/{total, number}",
                  },
                  { selected: selectedReadyCount, total: readyCount }
                )}
              </Button>
            }
          />
          <TooltipContent side="top">{toggleAllLabel}</TooltipContent>
        </Tooltip>
      ) : null}
      {filterable && !filterOpen ? (
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                ref={(node) => {
                  if (!node || !refocusFilterButton.current) return
                  refocusFilterButton.current = false
                  node.focus()
                }}
                type="button"
                size="icon-sm"
                variant="ghost"
                className="text-muted-foreground"
                aria-label={intl.formatMessage({
                  id: "sources_filter_open_aria",
                  defaultMessage: "Filter sources",
                })}
                onClick={() => setFilterOpen(true)}
              >
                <SearchIcon />
              </Button>
            }
          />
          <TooltipContent side="top">
            {intl.formatMessage({
              id: "sources_filter_open_tooltip",
              defaultMessage: "Filter sources",
            })}
          </TooltipContent>
        </Tooltip>
      ) : null}
      <AddSourcesMenu
        upload={upload}
        onNewFolder={
          organizing ? () => folderRowActions?.onNewFolder(null) : undefined
        }
        onNewNote={notes ? () => openNote(null) : undefined}
      />
    </div>
  )

  return (
    <>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>
            {intl.formatMessage({
              id: "sources_action_failed_title",
              defaultMessage: "Source action failed",
            })}
          </AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <section
        className="group/sources relative flex h-full min-h-0 w-full min-w-0 flex-col"
        aria-labelledby="all-sources"
        {...drop.handlers}
      >
        {drop.active ? (
          <div
            className={cn(
              "pointer-events-none absolute inset-0 z-10 flex justify-center rounded-xl border-2 border-dashed border-ring/60 p-4 text-center text-sm text-muted-foreground",
              // Folder rows stay in sight, since a drop on one files into it.
              hasFolders
                ? "items-end bg-app-shell/40"
                : "items-center bg-app-shell"
            )}
          >
            <span
              className={cn(hasFolders && "rounded-md bg-app-shell px-2 py-1")}
            >
              {intl.formatMessage({
                id: "sources_drop_label",
                defaultMessage: "Drop files to add them as sources",
              })}
            </span>
          </div>
        ) : null}
        {listHeader}
        <ScrollFade className="min-h-0 flex-1">
          {isLoading ? (
            <SkeletonSlabs />
          ) : documents.length > 0 || hasFolders ? (
            <SourceTree
              index={index}
              expanded={expanded}
              onExpandedChange={setFolderExpanded}
              filter={filter}
              selectedDocumentIds={selectedDocumentIdSet}
              folderTicks={folderTicks ?? new Map()}
              highlightedDocumentId={highlightedDocumentId}
              isDeleting={isDeleting}
              labelledBy="all-sources"
              documentActions={{
                onOpen,
                onPreview,
                onReveal,
                onRetry,
                onCancel,
                onDelete: (document) => {
                  setDeleteTarget(document)
                  setDeleteOpen(true)
                },
                onRename: onRename
                  ? (document) => {
                      setRenameTarget(document)
                      setRenameOpen(true)
                    }
                  : undefined,
                onEditNote: notes ? (id) => openNote(id) : undefined,
                onSelectionChange,
              }}
              folderActions={folderRowActions}
            />
          ) : (
            <Empty className="min-h-0 border-0 px-2">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FilePlus2Icon />
                </EmptyMedia>
                <EmptyTitle>
                  {intl.formatMessage({
                    id: "sources_list_empty",
                    defaultMessage: "No sources yet",
                  })}
                </EmptyTitle>
                <EmptyDescription>
                  {intl.formatMessage({
                    id: "sources_list_empty_body",
                    defaultMessage:
                      "Files and notes added to this workspace will appear here.",
                  })}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </ScrollFade>
      </section>
      <AlertDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onOpenChangeComplete={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage(
                {
                  id: "sources_delete_dialog_title",
                  defaultMessage:
                    "Delete {count, plural, one {# source} other {# sources}}?",
                },
                { count: deleteCount }
              )}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget === "selected"
                ? intl.formatMessage({
                    id: "sources_delete_dialog_selected_body",
                    defaultMessage:
                      "This permanently deletes the selected sources and their indexed data.",
                  })
                : deleteTarget
                  ? intl.formatMessage(
                      {
                        id: "sources_delete_dialog_named_body",
                        defaultMessage:
                          "This permanently deletes {title} and its indexed data.",
                      },
                      {
                        title: deleteTarget.title,
                      }
                    )
                  : intl.formatMessage({
                      id: "sources_delete_dialog_unnamed_body",
                      defaultMessage:
                        "This permanently deletes this source and its indexed data.",
                    })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "sources_delete_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleteTarget === "selected") onDeleteSelected()
                else if (deleteTarget) onDelete(deleteTarget.id)
              }}
            >
              {intl.formatMessage(
                {
                  id: "sources_delete_dialog_confirm_button",
                  defaultMessage:
                    "Delete {count, plural, one {source} other {sources}}",
                },
                {
                  count: deleteCount,
                }
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {onRename ? (
        <RenameSourceDialog
          document={renameTarget}
          open={renameOpen}
          onOpenChange={setRenameOpen}
          onOpenChangeComplete={(open) => {
            if (!open) setRenameTarget(null)
          }}
          onRename={onRename}
        />
      ) : null}
      {notes ? (
        <NoteEditorDialog
          target={noteTarget}
          open={noteOpen}
          notes={notes}
          onOpenChange={setNoteOpen}
          onOpenChangeComplete={(open) => {
            if (!open) setNoteTarget(null)
          }}
        />
      ) : null}
      {folderActions ? (
        <>
          <FolderNameDialog
            target={folderNameTarget}
            open={folderNameOpen}
            onOpenChange={setFolderNameOpen}
            onOpenChangeComplete={(open) => {
              if (!open) setFolderNameTarget(null)
            }}
            onSubmit={async (target, name) => {
              if (target.kind === "rename") {
                return folderActions.rename(target.folderId, name)
              }
              const created = await folderActions.create(
                folderIdFor(index, target.parentId),
                name
              )
              if (created && target.parentId !== null) {
                setFolderExpanded(target.parentId, true)
              }
              return created
            }}
          />
          <MoveToDialog
            index={index}
            target={moveTarget}
            open={moveOpen}
            onOpenChange={setMoveOpen}
            onOpenChangeComplete={(open) => {
              if (!open) setMoveTarget(null)
            }}
            onMove={(target, to) => moveInto(target, to)}
          />
          <DeleteFolderDialog
            target={folderDeleteTarget}
            open={folderDeleteOpen}
            onOpenChange={setFolderDeleteOpen}
            onOpenChangeComplete={(open) => {
              if (!open) setFolderDeleteTarget(null)
            }}
            onDelete={(folderId) => void folderActions.remove(folderId)}
          />
        </>
      ) : null}
    </>
  )
}
