import { useRef, useState, type ChangeEvent, type ReactNode } from "react"
import {
  ArrowLeftIcon,
  CheckCircle2Icon,
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import type { UploadOutcome, DocumentDetail, WorkspaceDocument } from "./api"
import type { Citation } from "@/features/chat/sse"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

const statusVariant = {
  pending: "outline",
  processing: "secondary",
  ready: "secondary",
  failed: "destructive",
} as const

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
  const selectable = document.status === "ready"

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-accent",
        selected && "bg-accent"
      )}
    >
      <button
        type="button"
        className="flex min-w-0 flex-1 items-center gap-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        onClick={onOpen}
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted">
          {document.document_type === "NOTE" ? (
            <NotebookTextIcon className="size-3.5" />
          ) : (
            <FileIcon className="size-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">
            {document.title}
          </span>
          <span className="mt-0.5 flex items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">
              {document.document_type === "NOTE" ? "Note" : "File"}
            </span>
            <Badge
              variant={statusVariant[document.status]}
              className="h-4 px-1.5 text-[10px]"
            >
              {document.status}
            </Badge>
          </span>
        </span>
      </button>
      {document.status === "failed" ? (
        <Button
          size="icon-xs"
          variant="ghost"
          aria-label={`Retry ${document.title}`}
          onClick={onRetry}
        >
          <RefreshCwIcon />
        </Button>
      ) : null}
      <Checkbox
        checked={selected}
        disabled={!selectable}
        aria-label={`Select ${document.title}`}
        onCheckedChange={(checked) => onSelectedChange(checked === true)}
      />
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
  uploadOutcome,
  error,
  onOpen,
  onBack,
  onRetry,
  onDeleteSelected,
  onSelectionChange,
  onUpload,
  onDismissUploadOutcome,
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
  uploadOutcome: UploadOutcome | null
  error: string | null
  onOpen: (documentId: number, citation?: Citation) => void
  onBack: () => void
  onRetry: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
  onUpload: (files: File[]) => void
  onDismissUploadOutcome: () => void
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
        <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:h-full">
          <div className="flex min-h-full flex-col gap-3 p-3">
            {uploadOutcome ? (
              <Alert>
                <CheckCircle2Icon />
                <AlertTitle>
                  {uploadOutcome.created.length > 0
                    ? `${uploadOutcome.created.length} source${uploadOutcome.created.length === 1 ? "" : "s"} added`
                    : "No new sources added"}
                </AlertTitle>
                <AlertDescription>
                  {uploadOutcome.created.length > 0 ? (
                    <p>Ingestion is running in the background.</p>
                  ) : null}
                  {uploadOutcome.duplicates.length > 0 ? (
                    <p>
                      Already present:{" "}
                      {uploadOutcome.duplicates
                        .map((duplicate) => duplicate.filename)
                        .join(", ")}
                    </p>
                  ) : null}
                  <Button
                    variant="link"
                    size="xs"
                    className="mt-1 h-auto p-0"
                    onClick={onDismissUploadOutcome}
                  >
                    Dismiss
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}
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
              <section aria-labelledby="all-sources">
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
