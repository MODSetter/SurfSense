import { memo, useCallback, useRef, useState } from "react"
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
import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
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
import type { MoveTarget } from "./move-to-dialog"
import type { FolderKey } from "./source-index"
import type { DocumentRowActions } from "./source-tree"
import { treeItemProps, type TreePlace, type TreeRowEvents } from "./tree-item"
import { useRowDrag } from "./use-row-drag"

// Memoized on plain values and the tree's stable callbacks, so a render of
// the tree renders only the rows whose values changed.
export const DocumentRow = memo(function DocumentRow({
  rowKey,
  level,
  setSize,
  posInSet,
  tabbable,
  document,
  parent,
  selected,
  highlighted,
  isDeleting,
  movable,
  takesFiles,
  events,
  actions,
  onMoveRequest,
}: TreePlace & {
  document: WorkspaceDocument
  // The folder the row sits in, where a drop on it files.
  parent: FolderKey
  selected: boolean
  highlighted: boolean
  isDeleting: boolean
  // Absent folders to move into, the row neither drags nor takes rows.
  movable: boolean
  // False while an upload runs, as the panel refuses files then.
  takesFiles: boolean
  events: TreeRowEvents
  actions: DocumentRowActions
  // Absent with no folders to move to.
  onMoveRequest?: (target: MoveTarget) => void
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
  const element = useRef<HTMLLIElement | null>(null)
  const { register } = events
  // Stable, so React never detaches and attaches the row again on a render.
  const ref = useCallback(
    (node: HTMLLIElement) => {
      element.current = node
      const release = register(rowKey, node)
      return () => {
        element.current = null
        release()
      }
    },
    [register, rowKey]
  )
  useRowDrag({
    rowRef: element,
    source: { kind: "document", id: document.id },
    name: document.title,
    drag: { into: parent, movable, takesFiles },
  })

  const onOpen = () => actions.onOpen(document.id)
  const onPreview = () => actions.onPreview?.(document.id)
  const onReveal = () => actions.onReveal(document.id)
  const onRetry = () => actions.onRetry(document.id)
  const onCancel = () => actions.onCancel(document.id)
  const onDelete = () => actions.onDelete(document)
  const onSelectedChange = (next: boolean) =>
    actions.onSelectionChange(document.id, next)
  const { onRename: rename, onEditNote: editNote } = actions
  const onRename = rename ? () => rename(document) : undefined
  const onEditNote = editNote ? () => editNote(document.id) : undefined
  const onMove = onMoveRequest
    ? () =>
        onMoveRequest({
          kind: "document",
          id: document.id,
          name: document.title,
          from: parent,
        })
    : undefined

  return (
    <Tooltip open={retryable && modifierHeld && rowHovered}>
      <TooltipTrigger
        render={
          <li
            {...treeItemProps(
              { rowKey, level, setSize, posInSet, tabbable },
              { label: document.title, checked: ready ? selected : undefined },
              events
            )}
            ref={ref}
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
            <OverflowTooltip
              label={document.title}
              focusOwner='[role="treeitem"]'
              render={
                <button
                  type="button"
                  disabled={!titleActionable}
                  className={cn(
                    "sidebar-row-title-fade min-w-0 flex-1 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
                    dropdownOpen && "sidebar-row-title-fade-actions"
                  )}
                  onClick={
                    titleActionable
                      ? previewable
                        ? onPreview
                        : onOpen
                      : undefined
                  }
                >
                  {document.title}
                </button>
              }
            />
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
})
