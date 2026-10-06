import { useRef, useState, type HTMLAttributes } from "react"
import {
  Alert02Icon,
  CancelCircleHalfDotIcon,
  CursorRemoveSelection02Icon,
  Edit02Icon,
  EllipsisIcon,
  ExternalLinkIcon,
  FolderOpenIcon,
  FolderTransferIcon,
  PencilIcon,
  RefreshCwIcon,
  SquareDashedMousePointerIcon,
  Trash2Icon,
  ViewIcon,
} from "@/components/ui/icons"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { getFileViewer } from "@/features/file-viewers/registry"
import { useModifierHeld } from "@/hooks/use-modifier-held"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { WorkspaceDocument } from "../api"
import { useRowDrag, type RowDrag } from "./use-row-drag"

export function DocumentRow({
  document,
  selected,
  highlighted,
  rowRef,
  onOpen,
  onPreview,
  onReveal,
  onRetry,
  onCancel,
  onDelete,
  onRename,
  onEditNote,
  isDeleting,
  onSelectedChange,
  onMove,
  itemProps,
  drag,
}: {
  document: WorkspaceDocument
  selected: boolean
  highlighted: boolean
  rowRef: (node: HTMLLIElement | null) => void
  onOpen: () => void
  onPreview: () => void
  onReveal: () => void
  onRetry: () => void
  onCancel: () => void
  onDelete: () => void
  onRename?: () => void
  onEditNote?: () => void
  isDeleting: boolean
  onSelectedChange: (selected: boolean) => void
  // Absent with no folders to move to.
  onMove?: () => void
  // The tree's own attributes for this row: role, level and focus.
  itemProps: HTMLAttributes<HTMLLIElement>
  drag: RowDrag
}) {
  const ready = document.status === "ready"
  const failed = document.status === "failed"
  const cancelled = document.status === "cancelled"
  const retryable = failed || cancelled
  const ingesting =
    document.status === "pending" || document.status === "processing"
  const processing = document.status === "processing"
  const openable = ready && document.document_type === "FILE"
  const previewable = getFileViewer(document.mime_type) !== null
  const titleActionable = previewable || openable
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [rowHovered, setRowHovered] = useState(false)
  // A developer aid: holding Ctrl/Cmd while hovering anywhere on a failed
  // row (not just the retry icon) surfaces the actual error above the row.
  const modifierHeld = useModifierHeld()
  const element = useRef<HTMLLIElement>(null)
  useRowDrag({
    rowRef: element,
    source: { kind: "document", id: document.id },
    name: document.title,
    drag,
  })

  return (
    <Tooltip open={retryable && modifierHeld && rowHovered}>
      <TooltipTrigger
        render={
          <li
            {...itemProps}
            ref={(node) => {
              element.current = node
              rowRef(node)
            }}
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
                    {
                      id: "sources_row_select_aria",
                      defaultMessage: "Select {title}",
                    },
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
                    {
                      id: "sources_row_processing_aria",
                      defaultMessage: "Processing {title}",
                    },
                    {
                      title: document.title,
                    }
                  )}
                />
              ) : null}
              {retryable ? (
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        aria-label={
                          cancelled
                            ? intl.formatMessage(
                                {
                                  id: "sources_row_retry_cancelled_aria",
                                  defaultMessage: "Cancelled. Retry {title}",
                                },
                                {
                                  title: document.title,
                                }
                              )
                            : intl.formatMessage(
                                {
                                  id: "sources_row_retry_failed_aria",
                                  defaultMessage:
                                    "Ingestion failed. Retry {title}",
                                },
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
                    }
                  />
                  <TooltipContent side="top" collisionPadding={8}>
                    {cancelled
                      ? intl.formatMessage({
                          id: "sources_row_retry_cancelled_tooltip",
                          defaultMessage: "Cancelled. Retry again.",
                        })
                      : intl.formatMessage({
                          id: "sources_row_retry_failed_tooltip",
                          defaultMessage: "Ingestion failed. Retry again.",
                        })}
                  </TooltipContent>
                </Tooltip>
              ) : null}
            </span>
            <button
              type="button"
              disabled={!titleActionable}
              className={cn(
                "sidebar-row-title-fade min-w-0 flex-1 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
                dropdownOpen && "sidebar-row-title-fade-actions"
              )}
              onClick={
                titleActionable ? (previewable ? onPreview : onOpen) : undefined
              }
            >
              {document.title}
            </button>
            <div className="absolute inset-y-0 right-0 flex items-center pr-1">
              <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                <DropdownMenuTrigger
                  render={
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      className="size-6 shrink-0 opacity-0 group-hover/source:opacity-100 hover:bg-transparent focus-visible:opacity-100 active:translate-y-px data-popup-open:bg-accent data-popup-open:opacity-100"
                      aria-label={intl.formatMessage(
                        {
                          id: "sources_row_actions_aria",
                          defaultMessage: "Actions for {title}",
                        },
                        {
                          title: document.title,
                        }
                      )}
                    >
                      <EllipsisIcon />
                    </Button>
                  }
                />
                <DropdownMenuContent
                  align="end"
                  sideOffset={8}
                  className="min-w-40"
                >
                  <DropdownMenuGroup>
                    {previewable ? (
                      <DropdownMenuItem onClick={onPreview}>
                        <ViewIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_preview_label",
                          defaultMessage: "Preview",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {openable ? (
                      <>
                        <DropdownMenuItem onClick={onOpen}>
                          <ExternalLinkIcon />
                          {intl.formatMessage({
                            id: "sources_row_menu_open_label",
                            defaultMessage: "Open",
                          })}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={onReveal}>
                          <FolderOpenIcon />
                          {intl.formatMessage({
                            id: "sources_row_menu_reveal_label",
                            defaultMessage: "Show in folder",
                          })}
                        </DropdownMenuItem>
                      </>
                    ) : null}
                    {ready ? (
                      <DropdownMenuItem
                        onClick={() => onSelectedChange(!selected)}
                      >
                        {selected ? (
                          <CursorRemoveSelection02Icon />
                        ) : (
                          <SquareDashedMousePointerIcon />
                        )}
                        {selected
                          ? intl.formatMessage({
                              id: "sources_row_menu_deselect_label",
                              defaultMessage: "Deselect",
                            })
                          : intl.formatMessage({
                              id: "sources_row_menu_select_label",
                              defaultMessage: "Select",
                            })}
                      </DropdownMenuItem>
                    ) : null}
                    {retryable ? (
                      <DropdownMenuItem onClick={onRetry}>
                        <RefreshCwIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_retry_label",
                          defaultMessage: "Retry",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {ingesting ? (
                      <DropdownMenuItem onClick={onCancel}>
                        <CancelCircleHalfDotIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_cancel_label",
                          defaultMessage: "Cancel",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {onEditNote && document.document_type === "NOTE" ? (
                      <DropdownMenuItem onClick={onEditNote}>
                        <Edit02Icon />
                        {intl.formatMessage({
                          id: "sources_row_menu_edit_note_label",
                          defaultMessage: "Edit note",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {onMove ? (
                      <DropdownMenuItem onClick={onMove}>
                        <FolderTransferIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_move_label",
                          defaultMessage: "Move to…",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {onRename ? (
                      <DropdownMenuItem onClick={onRename}>
                        <PencilIcon />
                        {intl.formatMessage({
                          id: "sources_row_menu_rename_label",
                          defaultMessage: "Rename",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    <DropdownMenuItem
                      variant="destructive"
                      disabled={processing || isDeleting}
                      onClick={onDelete}
                    >
                      <Trash2Icon />
                      {intl.formatMessage({
                        id: "sources_row_menu_delete_label",
                        defaultMessage: "Delete",
                      })}
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </li>
        }
      />
      <TooltipContent side="top" collisionPadding={8}>
        {document.error_message ??
          (cancelled
            ? intl.formatMessage({
                id: "sources_row_cancelled_status",
                defaultMessage: "Cancelled",
              })
            : intl.formatMessage({
                id: "sources_row_failed_status",
                defaultMessage: "Ingestion failed",
              }))}
      </TooltipContent>
    </Tooltip>
  )
}
