import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react"
import {
  Alert02Icon,
  CancelCircleHalfDotIcon,
  CursorRemoveSelection02Icon,
  EllipsisIcon,
  FilePlus2Icon,
  FolderOpenIcon,
  RefreshCwIcon,
  SquareDashedMousePointerIcon,
  Trash2Icon,
  ViewIcon,
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
import { useModifierHeld } from "@/hooks/use-modifier-held"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

function SelectableSourceRow({
  document,
  selected,
  highlighted,
  rowRef,
  onOpen,
  onReveal,
  onRetry,
  onCancel,
  onDelete,
  isDeleting,
  onSelectedChange,
}: {
  document: WorkspaceDocument
  selected: boolean
  highlighted: boolean
  rowRef: (node: HTMLLIElement | null) => void
  onOpen: () => void
  onReveal: () => void
  onRetry: () => void
  onCancel: () => void
  onDelete: () => void
  isDeleting: boolean
  onSelectedChange: (selected: boolean) => void
}) {
  const ready = document.status === "ready"
  const failed = document.status === "failed"
  const cancelled = document.status === "cancelled"
  const retryable = failed || cancelled
  const ingesting =
    document.status === "pending" || document.status === "processing"
  const processing = document.status === "processing"
  const openable = ready && document.document_type === "FILE"
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [rowHovered, setRowHovered] = useState(false)
  // A developer aid: holding Ctrl/Cmd while hovering anywhere on a failed
  // row (not just the retry icon) surfaces the actual error above the row.
  const modifierHeld = useModifierHeld()

  return (
    <Tooltip open={retryable && modifierHeld && rowHovered}>
      <TooltipTrigger asChild>
        <li
          ref={rowRef}
          aria-current={highlighted ? "true" : undefined}
          className={cn(
            "group group/source relative flex h-8 w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 select-none hover:bg-muted dark:hover:bg-muted/50",
            highlighted && "border-ring",
            dropdownOpen && "bg-muted dark:bg-muted/50"
          )}
          onMouseEnter={() => setRowHovered(true)}
          onMouseLeave={() => setRowHovered(false)}
        >
          <span className="relative flex size-7 shrink-0 items-center justify-center">
            {ready ? (
              <Checkbox
                checked={selected}
                aria-label={intl.formatMessage(
                  { id: "sources_row_select_aria" },
                  {
                    title: document.title,
                  }
                )}
                onClick={(event) => event.stopPropagation()}
                onCheckedChange={(checked) =>
                  onSelectedChange(checked === true)
                }
              />
            ) : null}
            {ingesting ? (
              <Spinner
                className="size-4.5 text-muted-foreground"
                aria-label={intl.formatMessage(
                  { id: "sources_row_processing_aria" },
                  {
                    title: document.title,
                  }
                )}
              />
            ) : null}
            {retryable ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    aria-label={
                      cancelled
                        ? intl.formatMessage(
                            { id: "sources_row_retry_cancelled_aria" },
                            {
                              title: document.title,
                            }
                          )
                        : intl.formatMessage(
                            { id: "sources_row_retry_failed_aria" },
                            {
                              title: document.title,
                            }
                          )
                    }
                    className="relative hover:bg-transparent"
                    onClick={onRetry}
                  >
                    <Alert02Icon className="size-4.5 text-destructive transition-opacity duration-150 group-hover/source:opacity-0 group-focus-visible/button:opacity-0" />
                    <RefreshCwIcon className="absolute inset-0 m-auto size-4.5 text-muted-foreground opacity-0 transition-opacity duration-150 group-hover/source:opacity-100 group-focus-visible/button:opacity-100" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" collisionPadding={8}>
                  {cancelled
                    ? intl.formatMessage({
                        id: "sources_row_retry_cancelled_tooltip",
                      })
                    : intl.formatMessage({
                        id: "sources_row_retry_failed_tooltip",
                      })}
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
                  aria-label={intl.formatMessage(
                    { id: "sources_row_actions_aria" },
                    {
                      title: document.title,
                    }
                  )}
                >
                  <EllipsisIcon />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                sideOffset={8}
                className="min-w-40"
              >
                <DropdownMenuGroup>
                  {openable ? (
                    <>
                      <DropdownMenuItem onSelect={onOpen}>
                        <ViewIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_open_label",
                        })}
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={onReveal}>
                        <FolderOpenIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_reveal_label",
                        })}
                      </DropdownMenuItem>
                    </>
                  ) : null}
                  {ready ? (
                    <DropdownMenuItem
                      onSelect={() => onSelectedChange(!selected)}
                    >
                      {selected ? (
                        <CursorRemoveSelection02Icon />
                      ) : (
                        <SquareDashedMousePointerIcon />
                      )}
                      {selected
                        ? intl.formatMessage({
                            id: "sources_row_menu_deselect_label",
                          })
                        : intl.formatMessage({
                            id: "sources_row_menu_select_label",
                          })}
                    </DropdownMenuItem>
                  ) : null}
                  {retryable ? (
                    <DropdownMenuItem onSelect={onRetry}>
                      <RefreshCwIcon />
                      {intl.formatMessage({
                        id: "sources_row_menu_retry_label",
                      })}
                    </DropdownMenuItem>
                  ) : null}
                  {ingesting ? (
                    <DropdownMenuItem onSelect={onCancel}>
                      <CancelCircleHalfDotIcon />
                      {intl.formatMessage({
                        id: "sources_row_menu_cancel_label",
                      })}
                    </DropdownMenuItem>
                  ) : null}
                  <DropdownMenuItem
                    variant="destructive"
                    disabled={processing || isDeleting}
                    onSelect={onDelete}
                  >
                    <Trash2Icon />
                    {intl.formatMessage({
                      id: "sources_row_menu_delete_label",
                    })}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </li>
      </TooltipTrigger>
      <TooltipContent side="top" collisionPadding={8}>
        {document.error_message ??
          (cancelled
            ? intl.formatMessage({ id: "sources_row_cancelled_status" })
            : intl.formatMessage({ id: "sources_row_failed_status" }))}
      </TooltipContent>
    </Tooltip>
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
        aria-label={intl.formatMessage({ id: "sources_add_file_aria" })}
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
        {isUploading
          ? intl.formatMessage({ id: "sources_add_uploading_status" })
          : intl.formatMessage({ id: "sources_add_button" })}
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
  onCancel,
  onDelete,
  onDeleteSelected,
  onSelectionChange,
  onToggleAll,
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
  onCancel: (documentId: number) => void
  onDelete: (documentId: number) => void
  onDeleteSelected: () => void
  onSelectionChange: (documentId: number, selected: boolean) => void
  onToggleAll: () => void
}) {
  const sourceRows = useRef(new Map<number, HTMLLIElement>())
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
  const readyCount = documents.filter(
    (document) => document.status === "ready"
  ).length
  const allSelected =
    readyCount > 0 && selectedDocumentIds.length === readyCount
  const listHeader = (
    <div className="mb-2 flex min-h-7 shrink-0 items-center justify-between gap-2">
      <h3
        id="all-sources"
        className="px-1 text-sm font-medium text-muted-foreground"
      >
        {intl.formatMessage({ id: "sources_list_title" })}
      </h3>
      <div className="flex items-center gap-1">
        {readyCount > 0 ? (
          <Button
            type="button"
            size="xs"
            variant="ghost"
            className="text-muted-foreground"
            onClick={onToggleAll}
          >
            {allSelected
              ? intl.formatMessage({ id: "sources_list_deselect_all_button" })
              : intl.formatMessage({ id: "sources_list_select_all_button" })}
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
          <AlertTitle>
            {intl.formatMessage({ id: "sources_action_failed_title" })}
          </AlertTitle>
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
            <ul className="flex list-none flex-col gap-1">
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
                  onCancel={() => onCancel(document.id)}
                  onDelete={() => setDeleteTarget(document)}
                  isDeleting={isDeleting}
                  onSelectedChange={(selected) =>
                    onSelectionChange(document.id, selected)
                  }
                />
              ))}
            </ul>
          ) : (
            <Empty className="min-h-0 border-0 px-2">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FilePlus2Icon />
                </EmptyMedia>
                <EmptyTitle>
                  {intl.formatMessage({ id: "sources_list_empty" })}
                </EmptyTitle>
                <EmptyDescription>
                  {intl.formatMessage({ id: "sources_list_empty_body" })}
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
              {intl.formatMessage(
                { id: "sources_delete_dialog_title" },
                { count: deleteCount }
              )}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget === "selected"
                ? intl.formatMessage({
                    id: "sources_delete_dialog_selected_body",
                  })
                : deleteTarget
                  ? intl.formatMessage(
                      { id: "sources_delete_dialog_named_body" },
                      {
                        title: deleteTarget.title,
                      }
                    )
                  : intl.formatMessage({
                      id: "sources_delete_dialog_unnamed_body",
                    })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "sources_delete_dialog_cancel_button",
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
                { id: "sources_delete_dialog_confirm_button" },
                {
                  count: deleteCount,
                }
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
