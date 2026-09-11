import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react"
import {
  Alert02Icon,
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
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { SOURCE_FILE_ACCEPT, type WorkspaceDocument } from "./api"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
        "group group/source relative flex h-8 w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 select-none hover:bg-muted dark:hover:bg-muted/50",
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
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={`Ingestion failed. Retry ${document.title}`}
                className="relative hover:bg-transparent"
                onClick={onRetry}
              >
                <Alert02Icon className="size-4.5 text-destructive transition-opacity duration-150 group-hover/source:opacity-0 group-focus-visible/button:opacity-0" />
                <RefreshCwIcon className="absolute inset-0 m-auto size-4.5 text-muted-foreground opacity-0 transition-opacity duration-150 group-hover/source:opacity-100 group-focus-visible/button:opacity-100" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left" collisionPadding={8}>
              Ingestion failed. Retry
            </TooltipContent>
          </Tooltip>
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

export function SourcesAddButton({
  isUploading,
  onUpload,
}: {
  isUploading: boolean
  onUpload: (files: File[]) => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const chooseFiles = () => fileInput.current?.click()
  const uploadSelectedFiles = (event: ChangeEvent<HTMLInputElement>) => {
    onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }

  return (
    <>
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
        size="xs"
        variant="outline"
        disabled={isUploading}
        onClick={chooseFiles}
      >
        {isUploading ? <Spinner /> : <FilePlus2Icon />}
        {isUploading ? "Uploading..." : "Add"}
      </Button>
    </>
  )
}

export function SourcesPanel({
  documents,
  selectedDocumentIds,
  highlightedDocumentId,
  isLoading,
  isDeleting,
  error,
  addAction,
  onOpen,
  onReveal,
  onRetry,
  onDelete,
  onDeleteSelected,
  onSelectionChange,
}: {
  documents: WorkspaceDocument[]
  selectedDocumentIds: number[]
  highlightedDocumentId: number | null
  isLoading: boolean
  isDeleting: boolean
  error: string | null
  addAction?: ReactNode
  onOpen: (documentId: number) => void
  onReveal: (documentId: number) => void
  onRetry: (documentId: number) => void
  onDelete: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
}) {
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
  useEffect(() => {
    if (highlightedDocumentId === null) return
    sourceRows.current
      .get(highlightedDocumentId)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [highlightedDocumentId])

  const selectedDocumentIdSet = new Set(selectedDocumentIds)
  const listHeader = (
    <div className="mb-2 flex min-h-7 shrink-0 items-center justify-between gap-2">
      <h3
        id="all-sources"
        className="text-xs font-medium text-muted-foreground"
      >
        All sources
      </h3>
      <div className="flex items-center gap-1">
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
        {addAction}
      </div>
    </div>
  )

  return (
    <>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Source action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <section
        className="flex h-full min-h-0 w-full min-w-0 flex-col"
        aria-labelledby="all-sources"
      >
        {listHeader}
        <ScrollShadow className="min-h-0 flex-1" from="from-background">
          {isLoading ? (
            <SkeletonSlabs />
          ) : documents.length > 0 ? (
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
          ) : (
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
          )}
        </ScrollShadow>
      </section>
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
