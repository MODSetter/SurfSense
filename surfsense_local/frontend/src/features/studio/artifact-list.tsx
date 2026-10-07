import { useMemo, useState } from "react"
import {
  Alert02Icon,
  CancelCircleHalfDotIcon,
  EllipsisIcon,
  FileIcon,
  FileTextIcon,
  FilterIcon,
  RefreshCwIcon,
  Trash2Icon,
  ViewIcon,
} from "@/components/ui/icons"

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
import { RelativeTime } from "@/components/relative-time"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useModifierHeld } from "@/hooks/use-modifier-held"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Artifact, StudioFormat } from "./api"
import {
  artifactLines,
  newestReady,
  type ArtifactLine,
} from "./artifact-versions"
import { canRetry } from "./can-retry"
import { FORMAT_ICONS, formatLabel } from "./studio-formats"

function artifactFilterKey(workspaceId: number) {
  return `surfsense:artifact-filter:${workspaceId}:v1`
}

function readStoredFormats(workspaceId: number): string[] {
  try {
    const parsed: unknown = JSON.parse(
      localStorage.getItem(artifactFilterKey(workspaceId)) ?? "[]"
    )
    return Array.isArray(parsed)
      ? parsed.filter((v) => typeof v === "string")
      : []
  } catch {
    return []
  }
}

function writeStoredFormats(workspaceId: number, formats: string[]) {
  try {
    localStorage.setItem(
      artifactFilterKey(workspaceId),
      JSON.stringify(formats)
    )
  } catch {
    // Private browsing and full disks throw.
  }
}

// A version mid-run would be deleted under its job.
function canDeleteLine(line: ArtifactLine) {
  return line.versions.every((version) => version.status !== "processing")
}

/** The version a document's row stands for: its newest, unless that one
 *  failed and an earlier one is ready, since the document still works. */
function shownVersion(line: ArtifactLine): Artifact {
  const ready = newestReady(line.versions)
  return line.newest.status === "failed" && ready ? ready : line.newest
}

function ArtifactRow({
  artifact,
  failedEdit,
  canDelete,
  onOpen,
  onRegenerate,
  onCancel,
  onDelete,
}: {
  /** The version the row stands for; its status is the row's. */
  artifact: Artifact
  /** A newer version than `artifact` that failed, or null. */
  failedEdit: Artifact | null
  canDelete: boolean
  /** Null while no version of the document has finished. */
  onOpen: (() => void) | null
  onRegenerate: (id: number) => void
  onCancel: () => void
  onDelete: () => void
}) {
  const ready = artifact.status === "ready"
  const failed = artifact.status === "failed"
  const cancelled = artifact.status === "cancelled"
  const retryable = canRetry(artifact)
  // What the developer tooltip explains: the failed edit, or the row's own end.
  const problem = failedEdit ?? (failed || cancelled ? artifact : null)
  const ingesting =
    artifact.status === "pending" || artifact.status === "processing"
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [rowHovered, setRowHovered] = useState(false)
  // A developer aid: holding Ctrl/Cmd while hovering anywhere on a failed
  // row (not just the retry icon) surfaces the actual error above the row.
  const modifierHeld = useModifierHeld()
  const FormatIcon = FORMAT_ICONS[artifact.format] ?? FileIcon

  return (
    <Tooltip open={problem !== null && modifierHeld && rowHovered}>
      <TooltipTrigger
        render={
          <li
            className={cn(
              "group group/artifact relative flex h-8 w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 hover:bg-muted dark:hover:bg-muted/50",
              dropdownOpen && "bg-muted dark:bg-muted/50"
            )}
            onMouseEnter={() => setRowHovered(true)}
            onMouseLeave={() => setRowHovered(false)}
          >
            <span className="relative flex size-7 shrink-0 items-center justify-center">
              {ready ? (
                <FormatIcon className="size-4.5 text-muted-foreground" />
              ) : null}
              {ingesting ? (
                <Spinner
                  className="size-4.5 text-muted-foreground"
                  aria-label={intl.formatMessage(
                    {
                      id: "studio_artifact_row_processing_aria",
                      defaultMessage: "Processing {name}",
                    },
                    {
                      name: artifact.title,
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
                                  id: "studio_artifact_row_retry_cancelled_aria",
                                  defaultMessage: "Cancelled. Retry {name}",
                                },
                                {
                                  name: artifact.title,
                                }
                              )
                            : intl.formatMessage(
                                {
                                  id: "studio_artifact_row_retry_failed_aria",
                                  defaultMessage:
                                    "Generation failed. Retry {name}",
                                },
                                {
                                  name: artifact.title,
                                }
                              )
                        }
                        className="relative hover:bg-transparent"
                        onClick={() => onRegenerate(artifact.id)}
                      >
                        <Alert02Icon className="size-4.5 text-destructive transition-opacity duration-150 group-hover/artifact:opacity-0 group-focus-visible/button:opacity-0" />
                        <RefreshCwIcon className="absolute inset-0 m-auto size-4.5 text-muted-foreground opacity-0 transition-opacity duration-150 group-hover/artifact:opacity-100 group-focus-visible/button:opacity-100" />
                      </Button>
                    }
                  />
                  <TooltipContent side="top" collisionPadding={8}>
                    {cancelled
                      ? intl.formatMessage({
                          id: "studio_artifact_row_retry_cancelled_tooltip",
                          defaultMessage: "Cancelled. Retry again.",
                        })
                      : intl.formatMessage({
                          id: "studio_artifact_row_retry_failed_tooltip",
                          defaultMessage: "Generation failed. Retry again.",
                        })}
                  </TooltipContent>
                </Tooltip>
              ) : null}
              {failed && !retryable ? (
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <span
                        role="img"
                        tabIndex={0}
                        aria-label={intl.formatMessage(
                          {
                            id: "studio_artifact_row_script_failed_aria",
                            defaultMessage: "Generation failed for {name}",
                          },
                          { name: artifact.title }
                        )}
                        className="flex rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        <Alert02Icon className="size-4.5 text-destructive" />
                      </span>
                    }
                  />
                  <TooltipContent side="top" collisionPadding={8}>
                    {intl.formatMessage({
                      id: "studio_artifact_row_script_failed_tooltip",
                      defaultMessage:
                        "The document script failed. Ask the agent to fix it.",
                    })}
                  </TooltipContent>
                </Tooltip>
              ) : null}
            </span>
            <OverflowTooltip
              label={artifact.title}
              render={
                <button
                  type="button"
                  disabled={!onOpen}
                  className={cn(
                    "sidebar-row-title-fade min-w-0 flex-1 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
                    dropdownOpen && "sidebar-row-title-fade-actions"
                  )}
                  onClick={onOpen ?? undefined}
                >
                  {artifact.title}
                </button>
              }
            />
            {artifact.version ? (
              <Badge
                variant="secondary"
                className="h-4 shrink-0 px-1.5 text-[10px] tabular-nums"
              >
                {intl.formatMessage(
                  {
                    id: "studio_artifact_row_version_label",
                    defaultMessage: "v{version, number}",
                  },
                  { version: artifact.version.number }
                )}
              </Badge>
            ) : null}
            {failedEdit?.version && artifact.version ? (
              <FailedEditHint
                failed={failedEdit.version.number}
                shown={artifact.version.number}
              />
            ) : null}
            {/* Two runs of one format share a title; the date tells them apart. */}
            <RelativeTime
              date={new Date(artifact.created_at)}
              compact
              showTooltip={false}
              className={cn(
                "shrink-0 text-[11px] text-muted-foreground/70 tabular-nums transition-opacity group-focus-within/artifact:opacity-0 group-hover/artifact:opacity-0",
                dropdownOpen && "opacity-0"
              )}
            />
            <div className="absolute inset-y-0 right-0 flex items-center pr-1">
              <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                <DropdownMenuTrigger
                  render={
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      className="size-6 shrink-0 opacity-0 group-hover/artifact:opacity-100 hover:bg-transparent focus-visible:opacity-100 active:translate-y-px data-popup-open:bg-accent data-popup-open:opacity-100"
                      aria-label={intl.formatMessage(
                        {
                          id: "studio_artifact_row_actions_aria",
                          defaultMessage: "Actions for {name}",
                        },
                        {
                          name: artifact.title,
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
                    {onOpen ? (
                      <DropdownMenuItem onClick={onOpen}>
                        <ViewIcon />
                        {intl.formatMessage({
                          id: "studio_artifact_row_open_label",
                          defaultMessage: "Open",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    {ready || retryable ? (
                      // One route, two words: after a failure it is a retry,
                      // after a success a fresh run of the same job.
                      <DropdownMenuItem
                        onClick={() => onRegenerate(artifact.id)}
                      >
                        <RefreshCwIcon />
                        {ready
                          ? intl.formatMessage({
                              id: "studio_artifact_row_regenerate_label",
                              defaultMessage: "Regenerate",
                            })
                          : intl.formatMessage({
                              id: "studio_artifact_row_retry_label",
                              defaultMessage: "Retry",
                            })}
                      </DropdownMenuItem>
                    ) : null}
                    {failedEdit?.version && canRetry(failedEdit) ? (
                      <DropdownMenuItem
                        onClick={() => onRegenerate(failedEdit.id)}
                      >
                        <RefreshCwIcon />
                        {intl.formatMessage(
                          {
                            id: "studio_artifact_row_retry_version_label",
                            defaultMessage: "Retry v{version, number}",
                          },
                          { version: failedEdit.version.number }
                        )}
                      </DropdownMenuItem>
                    ) : null}
                    {ingesting ? (
                      <DropdownMenuItem onClick={onCancel}>
                        <CancelCircleHalfDotIcon />
                        {intl.formatMessage({
                          id: "studio_artifact_row_cancel_label",
                          defaultMessage: "Cancel",
                        })}
                      </DropdownMenuItem>
                    ) : null}
                    <DropdownMenuItem
                      variant="destructive"
                      disabled={!canDelete}
                      onClick={onDelete}
                    >
                      <Trash2Icon />
                      {intl.formatMessage({
                        id: "studio_artifact_row_delete_label",
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
        {problem?.error_message ??
          (problem?.status === "cancelled"
            ? intl.formatMessage({
                id: "studio_artifact_row_cancelled_tooltip",
                defaultMessage: "Cancelled",
              })
            : intl.formatMessage({
                id: "studio_artifact_row_failed_tooltip",
                defaultMessage: "Generation failed",
              }))}
      </TooltipContent>
    </Tooltip>
  )
}

/** A quiet mark for an edit that failed after the version the row shows. */
function FailedEditHint({ failed, shown }: { failed: number; shown: number }) {
  const hint = intl.formatMessage(
    {
      id: "studio_artifact_row_failed_edit_tooltip",
      defaultMessage:
        "Latest edit failed (v{failed, number}). Showing v{shown, number}.",
    },
    { failed, shown }
  )
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            role="img"
            tabIndex={0}
            aria-label={hint}
            className="flex shrink-0 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <Alert02Icon className="size-3.5 text-muted-foreground" />
          </span>
        }
      />
      <TooltipContent side="top" collisionPadding={8}>
        {hint}
      </TooltipContent>
    </Tooltip>
  )
}

function TypeFilter({
  formats,
  labels,
  selected,
  onToggle,
  onClear,
}: {
  formats: [string, number][]
  labels: Map<string, string>
  selected: string[]
  onToggle: (format: string, checked: boolean) => void
  onClear: () => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className={cn(
              "relative shrink-0 text-muted-foreground data-popup-open:bg-accent",
              selected.length > 0 && "text-foreground"
            )}
            aria-label={
              selected.length > 0
                ? intl.formatMessage(
                    {
                      id: "studio_type_filter_active_aria",
                      defaultMessage:
                        "Filter artifacts ({count, number} active)",
                    },
                    {
                      count: selected.length,
                    }
                  )
                : intl.formatMessage({
                    id: "studio_type_filter_aria",
                    defaultMessage: "Filter artifacts",
                  })
            }
          >
            <FilterIcon className="size-4" />
            {selected.length > 0 ? (
              <span className="absolute top-0.5 right-0.5 size-1.5 rounded-full bg-primary" />
            ) : null}
          </Button>
        }
      />
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-52 select-none"
      >
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {intl.formatMessage({
              id: "studio_type_filter_title",
              defaultMessage: "Filter by type",
            })}
          </DropdownMenuLabel>
          {formats.map(([format, count]) => {
            const FormatIcon = FORMAT_ICONS[format] ?? FileIcon
            return (
              <DropdownMenuCheckboxItem
                key={format}
                checked={selected.includes(format)}
                onCheckedChange={(checked) =>
                  onToggle(format, checked === true)
                }
              >
                <FormatIcon className="size-4 text-muted-foreground" />
                <span className="flex-1">
                  {formatLabel({
                    key: format,
                    label: labels.get(format) ?? format,
                  })}{" "}
                  <span className="text-muted-foreground">
                    ({intl.formatNumber(count)})
                  </span>
                </span>
              </DropdownMenuCheckboxItem>
            )
          })}
        </DropdownMenuGroup>
        {selected.length > 0 ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onClear}>
              {intl.formatMessage({
                id: "studio_type_filter_clear_label",
                defaultMessage: "Clear filter",
              })}
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ArtifactList({
  workspaceId,
  artifacts,
  formats = [],
  isLoading = false,
  onOpen,
  onRegenerate,
  onCancel,
  onDelete,
}: {
  workspaceId: number
  artifacts: Artifact[]
  formats?: StudioFormat[]
  isLoading?: boolean
  onOpen: (id: number) => void
  onRegenerate: (id: number) => void
  onCancel: (id: number) => void
  onDelete: (id: number) => void
}) {
  // The backend's format catalog is the single source of truth for labels;
  // fall back to the raw key only for a format the catalog doesn't know yet.
  const formatLabels = useMemo(
    () => new Map(formats.map((format) => [format.key, format.label])),
    [formats]
  )
  const [deleteAsked, setDeleteAsked] = useState<ArtifactLine | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [selectedFormats, setSelectedFormats] = useState<string[]>(() =>
    readStoredFormats(workspaceId)
  )
  // The list stays mounted across workspace switches, so re-load the filter
  // that workspace last saved instead of carrying the old one over. This is
  // the "adjust state during render" idiom React recommends in place of an
  // effect for resetting state when a prop changes.
  const [renderedWorkspaceId, setRenderedWorkspaceId] = useState(workspaceId)
  if (workspaceId !== renderedWorkspaceId) {
    setRenderedWorkspaceId(workspaceId)
    setSelectedFormats(readStoredFormats(workspaceId))
  }

  const lines = useMemo(() => artifactLines(artifacts), [artifacts])
  // The document as it is now, not as it was when the dialog opened: the
  // agent can add a version, or start one, while the user decides. Once it
  // is gone, the dialog keeps its words through the closing animation.
  const deleteNow = deleteAsked
    ? (lines.find((line) => line.key === deleteAsked.key) ?? null)
    : null
  const deleteTarget = deleteNow ?? deleteAsked

  const availableFormats = useMemo(() => {
    const counts = new Map<string, number>()
    for (const { newest } of lines) {
      counts.set(newest.format, (counts.get(newest.format) ?? 0) + 1)
    }
    return [...counts.entries()]
  }, [lines])

  // Filtered directly against what's selected, not intersected with what's
  // available — a filter saved in another workspace (e.g. "podcast") should
  // correctly show zero results here rather than silently showing everything.
  const visibleLines = useMemo(() => {
    if (selectedFormats.length === 0) return lines
    const wanted = new Set(selectedFormats)
    return lines.filter(({ newest }) => wanted.has(newest.format))
  }, [lines, selectedFormats])

  function toggleFormat(format: string, checked: boolean) {
    const next = checked
      ? [...selectedFormats, format]
      : selectedFormats.filter((candidate) => candidate !== format)
    setSelectedFormats(next)
    writeStoredFormats(workspaceId, next)
  }

  function clearFormats() {
    setSelectedFormats([])
    writeStoredFormats(workspaceId, [])
  }

  return (
    <section
      className="flex h-full min-h-0 w-full min-w-0 flex-col"
      aria-labelledby="all-artifacts"
    >
      <div className="mb-2 flex min-h-7 shrink-0 items-center justify-between gap-2">
        <h3
          id="all-artifacts"
          className="px-1 text-sm font-medium text-muted-foreground"
        >
          {intl.formatMessage({
            id: "studio_artifact_list_title",
            defaultMessage: "Artifacts",
          })}
        </h3>
        {/* One type is no choice at all; the filter appears with the second. */}
        {availableFormats.length > 1 ? (
          <TypeFilter
            formats={availableFormats}
            labels={formatLabels}
            selected={selectedFormats}
            onToggle={toggleFormat}
            onClear={clearFormats}
          />
        ) : null}
      </div>
      <ScrollFade className="min-h-0 flex-1">
        {isLoading ? (
          <SkeletonSlabs />
        ) : artifacts.length === 0 ? (
          <Empty className="min-h-0 border-0 px-2">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FileTextIcon />
              </EmptyMedia>
              <EmptyTitle>
                {intl.formatMessage({
                  id: "studio_artifact_list_empty",
                  defaultMessage: "No generated artifacts yet",
                })}
              </EmptyTitle>
              <EmptyDescription>
                {intl.formatMessage({
                  id: "studio_artifact_list_empty_body",
                  defaultMessage:
                    "Artifacts generated in Studio will appear here.",
                })}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : visibleLines.length === 0 ? (
          <Empty className="min-h-0 border-0 px-2">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FilterIcon />
              </EmptyMedia>
              <EmptyTitle>
                {intl.formatMessage({
                  id: "studio_artifact_list_filtered_empty",
                  defaultMessage: "No artifacts match this filter",
                })}
              </EmptyTitle>
              <EmptyDescription>
                <Button type="button" variant="link" onClick={clearFormats}>
                  {intl.formatMessage({
                    id: "studio_artifact_list_clear_filter_button",
                    defaultMessage: "Clear filter",
                  })}
                </Button>
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ul className="flex list-none flex-col gap-1">
            {visibleLines.map((line) => {
              const { newest, versions } = line
              const shown = shownVersion(line)
              const openable = newestReady(versions)
              return (
                <ArtifactRow
                  key={line.key}
                  artifact={shown}
                  failedEdit={shown === newest ? null : newest}
                  canDelete={canDeleteLine(line)}
                  onOpen={openable ? () => onOpen(openable.id) : null}
                  onRegenerate={onRegenerate}
                  onCancel={() => onCancel(newest.id)}
                  onDelete={() => {
                    setDeleteAsked(line)
                    setDeleteOpen(true)
                  }}
                />
              )
            })}
          </ul>
        )}
      </ScrollFade>
      <AlertDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onOpenChangeComplete={(open) => {
          if (!open) setDeleteAsked(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {deleteTarget
                ? intl.formatMessage(
                    {
                      id: "studio_delete_dialog_title",
                      defaultMessage: "Delete {name}?",
                    },
                    {
                      name: deleteTarget.newest.title,
                    }
                  )
                : intl.formatMessage({
                    id: "studio_delete_dialog_unnamed_title",
                    defaultMessage: "Delete this artifact?",
                  })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget && deleteTarget.versions.length > 1
                ? intl.formatMessage(
                    {
                      id: "studio_delete_dialog_versions_body",
                      defaultMessage:
                        "This permanently deletes all {count, plural, one {# version} other {# versions}} of {name} and their generated files.",
                    },
                    {
                      count: deleteTarget.versions.length,
                      name: deleteTarget.newest.title,
                    }
                  )
                : deleteTarget
                  ? intl.formatMessage(
                      {
                        id: "studio_delete_dialog_body",
                        defaultMessage:
                          "This permanently deletes {name} and its generated files.",
                      },
                      {
                        name: deleteTarget.newest.title,
                      }
                    )
                  : intl.formatMessage({
                      id: "studio_delete_dialog_unnamed_body",
                      defaultMessage:
                        "This permanently deletes this artifact and its generated files.",
                    })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "studio_delete_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={!deleteNow || !canDeleteLine(deleteNow)}
              onClick={() => {
                for (const version of deleteNow?.versions ?? []) {
                  onDelete(version.id)
                }
              }}
            >
              {intl.formatMessage({
                id: "studio_delete_dialog_confirm_button",
                defaultMessage: "Delete artifact",
              })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
