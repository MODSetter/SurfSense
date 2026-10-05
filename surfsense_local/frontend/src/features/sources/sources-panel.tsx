import {
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react"
import {
  FilePlus2Icon,
  FolderAddIcon,
  FolderUploadIcon,
  PencilEdit02Icon,
  SearchIcon,
} from "@/components/ui/icons"

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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { SOURCE_FILE_ACCEPT, type WorkspaceDocument } from "./api"
import type { UploadEntry } from "./folder-upload/upload-plan"
import {
  NoteEditorDialog,
  type NoteActions,
  type NoteTarget,
} from "./note-editor-dialog"
import { RenameSourceDialog } from "./rename-source-dialog"
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
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

// Past this many sources a flat list gets the name filter too.
const FILTER_FROM_SOURCES = 20

export function SourcesAddButton({
  isUploading,
  onUpload,
  onUploadFolder,
}: {
  isUploading: boolean
  onUpload: (files: File[]) => void
  // Absent, Add offers files only.
  onUploadFolder?: (entries: UploadEntry[]) => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const uploadSelectedFiles = (event: ChangeEvent<HTMLInputElement>) => {
    onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }
  const uploadSelectedFolder = (event: ChangeEvent<HTMLInputElement>) => {
    onUploadFolder?.(
      Array.from(event.target.files ?? []).map((file) => ({
        file,
        relativePath: file.webkitRelativePath || file.name,
      }))
    )
    event.target.value = ""
  }
  const label = isUploading
    ? intl.formatMessage({
        id: "sources_add_uploading_status",
        defaultMessage: "Uploading...",
      })
    : intl.formatMessage({
        id: "sources_add_button",
        defaultMessage: "Add",
      })

  return (
    <>
      <Input
        ref={fileInput}
        type="file"
        multiple
        accept={SOURCE_FILE_ACCEPT}
        className="sr-only"
        aria-label={intl.formatMessage({
          id: "sources_add_file_aria",
          defaultMessage: "Upload source files",
        })}
        disabled={isUploading}
        onChange={uploadSelectedFiles}
      />
      {onUploadFolder ? (
        <>
          <Input
            ref={(node) => {
              folderInput.current = node
              // React has no prop for it; Chromium picks a folder with it.
              node?.setAttribute("webkitdirectory", "")
            }}
            type="file"
            multiple
            className="sr-only"
            aria-label={intl.formatMessage({
              id: "sources_add_folder_aria",
              defaultMessage: "Upload a source folder",
            })}
            disabled={isUploading}
            onChange={uploadSelectedFolder}
          />
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button size="xs" variant="outline" disabled={isUploading}>
                  {isUploading ? <Spinner /> : <FilePlus2Icon />}
                  {label}
                </Button>
              }
            />
            <DropdownMenuContent
              align="end"
              sideOffset={6}
              className="min-w-40"
            >
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => fileInput.current?.click()}>
                  <FilePlus2Icon />
                  {intl.formatMessage({
                    id: "sources_add_files_label",
                    defaultMessage: "Files…",
                  })}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => folderInput.current?.click()}>
                  <FolderUploadIcon />
                  {intl.formatMessage({
                    id: "sources_add_folder_label",
                    defaultMessage: "Folder…",
                  })}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </>
      ) : (
        <Button
          size="xs"
          variant="outline"
          disabled={isUploading}
          onClick={() => fileInput.current?.click()}
        >
          {isUploading ? <Spinner /> : <FilePlus2Icon />}
          {label}
        </Button>
      )}
    </>
  )
}

export function SourcesPanel({
  documents,
  index: givenIndex,
  selectedDocumentIds,
  folderTicks,
  highlightedDocumentId,
  isLoading,
  isDeleting,
  error,
  addAction,
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
  addAction?: ReactNode
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
  const showFilter = hasFolders || documents.length > FILTER_FROM_SOURCES

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
  const readyCount = documents.filter(
    (document) => document.status === "ready"
  ).length
  const allSelected = folderTicks
    ? folderTicks.get(TOP_TICK) === "checked"
    : readyCount > 0 && selectedDocumentIds.length === readyCount
  const listHeader = (
    // Wraps to a second line, rather than clipping, once a language's Select
    // all / Deselect all no longer fits beside the title and Add.
    <div className="mb-2 flex min-h-7 shrink-0 flex-wrap items-center justify-between gap-x-2 gap-y-1">
      {/* The title takes nearly all spare room on a shared line, keeping the
      buttons together at the right; alone on the second line, the buttons get
      it all, so Add alone moves to the right edge. */}
      <h3
        id="all-sources"
        className="grow-999 px-1 text-sm font-medium text-muted-foreground"
      >
        {intl.formatMessage({
          id: "sources_list_title",
          defaultMessage: "Sources",
        })}
      </h3>
      <div className="flex grow items-center gap-1">
        {readyCount > 0 ? (
          <Button
            type="button"
            size="xs"
            variant="ghost"
            className="text-muted-foreground"
            onClick={onToggleAll}
          >
            {allSelected
              ? intl.formatMessage({
                  id: "sources_list_deselect_all_button",
                  defaultMessage: "Deselect all",
                })
              : intl.formatMessage({
                  id: "sources_list_select_all_button",
                  defaultMessage: "Select all",
                })}
          </Button>
        ) : null}
        <div className="ml-auto flex items-center gap-1">
          {notes ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => openNote(null)}
            >
              <PencilEdit02Icon data-icon="inline-start" />
              {intl.formatMessage({
                id: "sources_new_note_button",
                defaultMessage: "New note",
              })}
            </Button>
          ) : null}
          {organizing ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={intl.formatMessage({
                      id: "sources_new_folder_aria",
                      defaultMessage: "New folder",
                    })}
                    onClick={() => folderRowActions?.onNewFolder(null)}
                  >
                    <FolderAddIcon />
                  </Button>
                }
              />
              <TooltipContent side="top">
                {intl.formatMessage({
                  id: "sources_new_folder_tooltip",
                  defaultMessage: "New folder",
                })}
              </TooltipContent>
            </Tooltip>
          ) : null}
          {addAction}
        </div>
      </div>
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
        className="relative flex h-full min-h-0 w-full min-w-0 flex-col"
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
        {showFilter ? (
          <InputGroup className="mb-2 h-8 shrink-0">
            <InputGroupAddon>
              <SearchIcon />
            </InputGroupAddon>
            <InputGroupInput
              type="search"
              value={filter}
              placeholder={intl.formatMessage({
                id: "sources_filter_placeholder",
                defaultMessage: "Filter by name",
              })}
              aria-label={intl.formatMessage({
                id: "sources_filter_aria",
                defaultMessage: "Filter sources by name",
              })}
              onChange={(event) => setFilter(event.target.value)}
            />
          </InputGroup>
        ) : null}
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
