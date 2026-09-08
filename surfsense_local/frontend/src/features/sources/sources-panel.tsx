import { useRef, useState, type ChangeEvent, type ReactNode } from "react"
import {
  ArrowLeftIcon,
  EllipsisIcon,
  FileIcon,
  FilePlus2Icon,
  NotebookTextIcon,
  RefreshCwIcon,
  Trash2Icon,
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
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import {
  SOURCE_FILE_ACCEPT,
  type DocumentDetail,
  type WorkspaceDocument,
} from "./api"
import type { Citation } from "@/features/chat/sse"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

function SelectableSourceRow({
  document,
  selected,
  onOpen,
  onRetry,
  onSelectedChange,
}: {
  document: WorkspaceDocument
  selected: boolean
  onOpen: () => void
  onRetry: () => void
  onSelectedChange: (selected: boolean) => void
}) {
  const ready = document.status === "ready"
  const failed = document.status === "failed"
  const processing =
    document.status === "pending" || document.status === "processing"

  return (
    <div
      className={cn(
        "group/source flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-lg px-2 py-1.5 focus-within:bg-accent hover:bg-accent",
        selected && "bg-accent"
      )}
    >
      <span className="relative flex size-7 shrink-0 items-center justify-center">
        {ready ? (
          <>
            <span
              className={cn(
                "absolute inset-0 flex items-center justify-center text-muted-foreground transition-opacity duration-150",
                selected
                  ? "opacity-0"
                  : "opacity-100 group-focus-within/source:opacity-0 group-hover/source:opacity-0"
              )}
            >
              {document.document_type === "NOTE" ? (
                <NotebookTextIcon />
              ) : (
                <FileIcon />
              )}
            </span>
            <Checkbox
              checked={selected}
              aria-label={`Select ${document.title}`}
              className={cn(
                "absolute transition-opacity duration-150",
                selected
                  ? "opacity-100"
                  : "pointer-events-none opacity-0 group-focus-within/source:pointer-events-auto group-focus-within/source:opacity-100 group-hover/source:pointer-events-auto group-hover/source:opacity-100 focus-visible:pointer-events-auto focus-visible:opacity-100"
              )}
              onClick={(event) => event.stopPropagation()}
              onCheckedChange={(checked) => onSelectedChange(checked === true)}
            />
          </>
        ) : null}
        {processing ? (
          <Spinner
            className="text-muted-foreground"
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
            <RefreshCwIcon />
          </Button>
        ) : null}
      </span>
      <button
        type="button"
        disabled={!ready}
        className="min-w-0 flex-1 truncate rounded-sm text-left text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default"
        onClick={ready ? onOpen : undefined}
      >
        {document.title}
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="shrink-0"
            aria-label={`Actions for ${document.title}`}
          >
            <EllipsisIcon />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            {ready ? (
              <>
                <DropdownMenuItem onSelect={onOpen}>Open</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onSelectedChange(!selected)}>
                  {selected ? "Deselect" : "Select"}
                </DropdownMenuItem>
              </>
            ) : null}
            {failed ? (
              <DropdownMenuItem onSelect={onRetry}>Retry</DropdownMenuItem>
            ) : null}
            {processing ? (
              <DropdownMenuItem disabled>Processing</DropdownMenuItem>
            ) : null}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

function DocumentPreview({
  document,
  citation,
  onBack,
}: {
  document: DocumentDetail
  citation: Citation | null
  onBack: () => void
}) {
  const lines = (document.content ?? "").split("\n")
  return (
    <>
      <header className="flex h-14 items-center gap-2 border-b px-3">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Back to sources"
          onClick={onBack}
        >
          <ArrowLeftIcon />
        </Button>
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">
          {document.title}
        </h2>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="p-4">
          {document.content ? (
            <pre className="font-sans text-xs leading-6 whitespace-pre-wrap">
              {lines.map((line, index) => {
                const lineNumber = index + 1
                const cited =
                  citation?.start_line != null &&
                  citation.end_line != null &&
                  lineNumber >= citation.start_line &&
                  lineNumber <= citation.end_line
                return (
                  <span
                    key={lineNumber}
                    id={cited ? `cited-line-${lineNumber}` : undefined}
                    className={cn(
                      "block",
                      cited && "bg-chart-1/15 text-foreground"
                    )}
                  >
                    {line || " "}
                  </span>
                )
              })}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">
              No extracted text is available for this source.
            </p>
          )}
        </div>
      </ScrollArea>
    </>
  )
}

export function SourcesPanel({
  documents,
  selectedDocumentIds,
  selectedDocument,
  selectedCitation,
  isLoading,
  isLoadingPreview,
  isUploading,
  isDeleting,
  error,
  onOpen,
  onBack,
  onRetry,
  onDeleteSelected,
  onSelectionChange,
  onUpload,
  studioSlot,
}: {
  documents: WorkspaceDocument[]
  selectedDocumentIds: number[]
  selectedDocument: DocumentDetail | null
  selectedCitation: Citation | null
  isLoading: boolean
  isLoadingPreview: boolean
  isUploading: boolean
  isDeleting: boolean
  error: string | null
  onOpen: (documentId: number, citation?: Citation) => void
  onBack: () => void
  onRetry: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
  onUpload: (files: File[]) => void
  studioSlot?: ReactNode
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false)
  const chooseFiles = () => fileInput.current?.click()
  const uploadSelectedFiles = (event: ChangeEvent<HTMLInputElement>) => {
    onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }

  if (selectedDocument) {
    return (
      <aside
        className="flex h-full min-w-0 flex-col bg-card/30"
        aria-label="Source preview"
      >
        <DocumentPreview
          document={selectedDocument}
          citation={selectedCitation}
          onBack={onBack}
        />
      </aside>
    )
  }

  const selectedDocumentIdSet = new Set(selectedDocumentIds)

  return (
    <>
      <aside
        className="flex h-full min-w-0 flex-col bg-card/30"
        aria-label="Workspace sources"
      >
        <header className="flex h-14 items-center justify-between border-b px-4">
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
          <div className="flex items-center gap-2">
            {studioSlot}
            <Button
              size="sm"
              variant="outline"
              disabled={isUploading}
              onClick={chooseFiles}
            >
              {isUploading ? <Spinner /> : <FilePlus2Icon />}
              {isUploading ? "Uploading..." : "Add"}
            </Button>
          </div>
        </header>
        <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:!block [&_[data-slot=scroll-area-viewport]>div]:h-full [&_[data-slot=scroll-area-viewport]>div]:w-full">
          <div className="flex min-h-full w-full min-w-0 flex-col gap-3 overflow-hidden p-3">
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Source action failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {isLoading || isLoadingPreview
              ? [0, 1, 2].map((item) => (
                  <Skeleton key={item} className="h-20 w-full" />
                ))
              : null}
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
                      onClick={() => setDeleteConfirmationOpen(true)}
                    >
                      <Trash2Icon data-icon="inline-start" />
                      Delete {selectedDocumentIds.length}
                    </Button>
                  ) : null}
                </div>
                <div className="flex flex-col gap-1">
                  {documents.map((document) => (
                    <SelectableSourceRow
                      key={document.id}
                      document={document}
                      selected={selectedDocumentIdSet.has(document.id)}
                      onOpen={() => onOpen(document.id)}
                      onRetry={() => onRetry(document.id)}
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
        </ScrollArea>
      </aside>
      <AlertDialog
        open={deleteConfirmationOpen}
        onOpenChange={setDeleteConfirmationOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedDocumentIds.length}{" "}
              {selectedDocumentIds.length === 1 ? "source" : "sources"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the selected sources and their indexed
              data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={onDeleteSelected}>
              Delete sources
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
