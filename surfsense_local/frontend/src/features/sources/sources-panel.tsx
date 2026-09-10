import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react"
import {
  EllipsisIcon,
  FileIcon,
  FilePlus2Icon,
  FolderOpenIcon,
  Loader2Icon,
  NotebookTextIcon,
  RefreshCwIcon,
  SquareDashedMousePointerIcon,
  Trash2Icon,
  ViewIcon,
  XIcon,
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
import { Checkbox } from "@/components/ui/checkbox"
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
import { Skeleton } from "@/components/ui/skeleton"
import { SOURCE_FILE_ACCEPT, type WorkspaceDocument } from "./api"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

function SelectableSourceRow({
  document,
  selected,
  highlighted,
  rowRef,
  onOpen,
  onReveal,
  onRetry,
  onDelete,
  isDeleting,
  onSelectedChange,
}: {
  document: WorkspaceDocument
  selected: boolean
  highlighted: boolean
  rowRef: (node: HTMLDivElement | null) => void
  onOpen: () => void
  onReveal: () => void
  onRetry: () => void
  onDelete: () => void
  isDeleting: boolean
  onSelectedChange: (selected: boolean) => void
}) {
  const ready = document.status === "ready"
  const failed = document.status === "failed"
  const ingesting =
    document.status === "pending" || document.status === "processing"
  const processing = document.status === "processing"
  const openable = ready && document.document_type === "FILE"
  const [dropdownOpen, setDropdownOpen] = useState(false)

  return (
    <div
      ref={rowRef}
      aria-current={highlighted ? "true" : undefined}
      className={cn(
        "group group/source relative flex h-8 w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 hover:bg-muted dark:hover:bg-muted/50",
        highlighted && "border-ring",
        selected && "bg-sidebar-accent text-white",
        dropdownOpen && "bg-muted dark:bg-muted/50"
      )}
    >
      <span className="relative flex size-7 shrink-0 items-center justify-center">
        {ready ? (
          <>
            <Checkbox
              checked={selected}
              aria-label={`Select ${document.title}`}
              className={cn(
                "peer absolute z-10 transition-opacity duration-150",
                selected
                  ? "opacity-100"
                  : "pointer-events-none opacity-0 group-hover/source:pointer-events-auto group-hover/source:opacity-100 focus-visible:pointer-events-auto focus-visible:opacity-100"
              )}
              onClick={(event) => event.stopPropagation()}
              onCheckedChange={(checked) => onSelectedChange(checked === true)}
            />
            <span
              className={cn(
                "pointer-events-none absolute inset-0 flex items-center justify-center text-muted-foreground transition-opacity duration-150",
                selected
                  ? "opacity-0"
                  : "opacity-100 group-hover/source:opacity-0 peer-focus-visible:opacity-0"
              )}
            >
              {document.document_type === "NOTE" ? (
                <NotebookTextIcon className="size-4.5" />
              ) : (
                <FileIcon className="size-4.5" />
              )}
            </span>
          </>
        ) : null}
        {ingesting ? (
          <Spinner
            className="size-4.5 text-muted-foreground"
            aria-label={`Processing ${document.title}`}
          />
        ) : null}
        {failed ? (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={`Retry ${document.title}`}
            onClick={onRetry}
          >
            <RefreshCwIcon className="size-4.5" />
          </Button>
        ) : null}
      </span>
      <button
        type="button"
        disabled={!openable}
        className={cn(
          "sidebar-row-title-fade min-w-0 flex-1 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
          dropdownOpen && "sidebar-row-title-fade-actions"
        )}
        onClick={openable ? onOpen : undefined}
      >
        {document.title}
      </button>
      <div className="absolute inset-y-0 right-0 flex items-center pr-1">
        <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              className="size-6 shrink-0 opacity-0 group-hover/source:opacity-100 hover:bg-transparent focus-visible:opacity-100 active:translate-y-px data-[state=open]:bg-accent data-[state=open]:opacity-100"
              aria-label={`Actions for ${document.title}`}
            >
              <EllipsisIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" sideOffset={8} className="min-w-40">
            <DropdownMenuGroup>
              {openable ? (
                <>
                  <DropdownMenuItem onSelect={onOpen}>
                    <ViewIcon />
                    Open
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={onReveal}>
                    <FolderOpenIcon />
                    Show in folder
                  </DropdownMenuItem>
                </>
              ) : null}
              {ready ? (
                <DropdownMenuItem onSelect={() => onSelectedChange(!selected)}>
                  {selected ? <XIcon /> : <SquareDashedMousePointerIcon />}
                  {selected ? "Deselect" : "Select"}
                </DropdownMenuItem>
              ) : null}
              {failed ? (
                <DropdownMenuItem onSelect={onRetry}>
                  <RefreshCwIcon />
                  Retry
                </DropdownMenuItem>
              ) : null}
              {ingesting ? (
                <DropdownMenuItem disabled>
                  <span className="flex animate-spin" aria-hidden="true">
                    <Loader2Icon />
                  </span>
                  Processing
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuItem
                variant="destructive"
                disabled={processing || isDeleting}
                onSelect={onDelete}
              >
                <Trash2Icon />
                Delete
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

export function SourcesPanel({
  documents,
  selectedDocumentIds,
  highlightedDocumentId,
  isLoading,
  isUploading,
  isDeleting,
  error,
  onOpen,
  onReveal,
  onRetry,
  onDelete,
  onDeleteSelected,
  onSelectionChange,
  onUpload,
  studioSlot,
}: {
  documents: WorkspaceDocument[]
  selectedDocumentIds: number[]
  highlightedDocumentId: number | null
  isLoading: boolean
  isUploading: boolean
  isDeleting: boolean
  error: string | null
  onOpen: (documentId: number) => void
  onReveal: (documentId: number) => void
  onRetry: (documentId: number) => void
  onDelete: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
  onUpload: (files: File[]) => void
  studioSlot?: ReactNode
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const sourceRows = useRef(new Map<number, HTMLDivElement>())
  const [deleteTarget, setDeleteTarget] = useState<
    WorkspaceDocument | "selected" | null
  >(null)
  const deleteCount =
    deleteTarget === "selected"
      ? selectedDocumentIds.length
      : deleteTarget
        ? 1
        : 0
  const chooseFiles = () => fileInput.current?.click()
  const uploadSelectedFiles = (event: ChangeEvent<HTMLInputElement>) => {
    onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }

  useEffect(() => {
    if (highlightedDocumentId === null) return
    sourceRows.current
      .get(highlightedDocumentId)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [highlightedDocumentId])

  const selectedDocumentIdSet = new Set(selectedDocumentIds)

  return (
    <>
      <aside
        className="flex h-full min-w-0 flex-col border-l bg-background"
        id="workspace-sources"
        aria-label="Workspace sources"
      >
        <header className="flex h-14 items-center justify-between border-b px-3">
          <h2 className="text-sm font-semibold">Sources</h2>
          <Input
            ref={fileInput}
            type="file"
            multiple
            accept={SOURCE_FILE_ACCEPT}
            className="sr-only"
            aria-label="Upload source files"
            disabled={isUploading}
            onChange={uploadSelectedFiles}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={isUploading}
            onClick={chooseFiles}
          >
            {isUploading ? <Spinner /> : <FilePlus2Icon />}
            {isUploading ? "Uploading..." : "Add"}
          </Button>
        </header>
        <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <div className="flex min-h-full w-full min-w-0 flex-col gap-3 overflow-hidden p-2">
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Source action failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {isLoading
              ? [0, 1, 2].map((item) => (
                  <Skeleton key={item} className="h-20 w-full" />
                ))
              : null}
            {studioSlot}
            {!isLoading && documents.length > 0 ? (
              <section
                className="w-full min-w-0 overflow-hidden"
                aria-labelledby="all-sources"
              >
                <div className="mb-2 flex min-h-7 items-center justify-between gap-2 px-1">
                  <h3
                    id="all-sources"
                    className="text-xs font-medium text-muted-foreground"
                  >
                    All sources
                  </h3>
                  {selectedDocumentIds.length > 0 ? (
                    <Button
                      size="xs"
                      variant="destructive"
                      disabled={isDeleting}
                      onClick={() => setDeleteTarget("selected")}
                    >
                      <Trash2Icon data-icon="inline-start" />
                      Delete ({selectedDocumentIds.length})
                    </Button>
                  ) : null}
                </div>
                <div className="flex flex-col gap-1">
                  {documents.map((document) => (
                    <SelectableSourceRow
                      key={document.id}
                      document={document}
                      selected={selectedDocumentIdSet.has(document.id)}
                      highlighted={highlightedDocumentId === document.id}
                      rowRef={(node) => {
                        if (node) sourceRows.current.set(document.id, node)
                        else sourceRows.current.delete(document.id)
                      }}
                      onOpen={() => onOpen(document.id)}
                      onReveal={() => onReveal(document.id)}
                      onRetry={() => onRetry(document.id)}
                      onDelete={() => setDeleteTarget(document)}
                      isDeleting={isDeleting}
                      onSelectedChange={(selected) =>
                        onSelectionChange(document.id, selected)
                      }
                    />
                  ))}
                </div>
              </section>
            ) : null}
            {!isLoading && documents.length === 0 ? (
              <Empty className="min-h-0 border-0 px-2">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <FilePlus2Icon />
                  </EmptyMedia>
                  <EmptyTitle>No sources yet</EmptyTitle>
                  <EmptyDescription>
                    Files and notes added to this workspace will appear here.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : null}
          </div>
        </div>
      </aside>
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {deleteCount} {deleteCount === 1 ? "source" : "sources"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget === "selected"
                ? "This permanently deletes the selected sources and their indexed data."
                : `This permanently deletes ${deleteTarget?.title ?? "this source"} and its indexed data.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleteTarget === "selected") onDeleteSelected()
                else if (deleteTarget) onDelete(deleteTarget.id)
              }}
            >
              Delete {deleteCount === 1 ? "source" : "sources"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
