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
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useModifierHeld } from "@/hooks/use-modifier-held"
import { cn } from "@/lib/utils"

import type { Artifact, StudioFormat } from "./api"
import { FORMAT_ICONS } from "./studio-formats"

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

function ArtifactRow({
  artifact,
  onOpen,
  onRegenerate,
  onCancel,
  onDelete,
}: {
  artifact: Artifact
  onOpen: () => void
  onRegenerate: () => void
  onCancel: () => void
  onDelete: () => void
}) {
  const ready = artifact.status === "ready"
  const failed = artifact.status === "failed"
  const cancelled = artifact.status === "cancelled"
  const retryable = failed || cancelled
  const ingesting =
    artifact.status === "pending" || artifact.status === "processing"
  const processing = artifact.status === "processing"
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [rowHovered, setRowHovered] = useState(false)
  // A developer aid: holding Ctrl/Cmd while hovering anywhere on a failed
  // row (not just the retry icon) surfaces the actual error above the row.
  const modifierHeld = useModifierHeld()
  const FormatIcon = FORMAT_ICONS[artifact.format] ?? FileIcon

  return (
    <Tooltip open={retryable && modifierHeld && rowHovered}>
      <TooltipTrigger asChild>
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
                aria-label={`Processing ${artifact.title}`}
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
                        ? `Cancelled. Retry ${artifact.title}`
                        : `Generation failed. Retry ${artifact.title}`
                    }
                    className="relative hover:bg-transparent"
                    onClick={onRegenerate}
                  >
                    <Alert02Icon className="size-4.5 text-destructive transition-opacity duration-150 group-hover/artifact:opacity-0 group-focus-visible/button:opacity-0" />
                    <RefreshCwIcon className="absolute inset-0 m-auto size-4.5 text-muted-foreground opacity-0 transition-opacity duration-150 group-hover/artifact:opacity-100 group-focus-visible/button:opacity-100" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" collisionPadding={8}>
                  {cancelled
                    ? "Cancelled. Retry again."
                    : "Generation failed. Retry again."}
                </TooltipContent>
              </Tooltip>
            ) : null}
          </span>
          <button
            type="button"
            disabled={!ready}
            className={cn(
              "sidebar-row-title-fade min-w-0 flex-1 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
              dropdownOpen && "sidebar-row-title-fade-actions"
            )}
            onClick={ready ? onOpen : undefined}
          >
            {artifact.title}
          </button>
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
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  className="size-6 shrink-0 opacity-0 group-hover/artifact:opacity-100 hover:bg-transparent focus-visible:opacity-100 active:translate-y-px data-[state=open]:bg-accent data-[state=open]:opacity-100"
                  aria-label={`Actions for ${artifact.title}`}
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
                  {ready ? (
                    <DropdownMenuItem onSelect={onOpen}>
                      <ViewIcon />
                      Open
                    </DropdownMenuItem>
                  ) : null}
                  {ready || retryable ? (
                    // One route, two words: after a failure it is a retry,
                    // after a success a fresh run of the same job.
                    <DropdownMenuItem onSelect={onRegenerate}>
                      <RefreshCwIcon />
                      {ready ? "Regenerate" : "Retry"}
                    </DropdownMenuItem>
                  ) : null}
                  {ingesting ? (
                    <DropdownMenuItem onSelect={onCancel}>
                      <CancelCircleHalfDotIcon />
                      Cancel
                    </DropdownMenuItem>
                  ) : null}
                  <DropdownMenuItem
                    variant="destructive"
                    disabled={processing}
                    onSelect={onDelete}
                  >
                    <Trash2Icon />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </li>
      </TooltipTrigger>
      <TooltipContent side="top" collisionPadding={8}>
        {artifact.error_message ??
          (cancelled ? "Cancelled" : "Generation failed")}
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
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          className={cn(
            "relative size-6 shrink-0 text-muted-foreground data-[state=open]:bg-accent",
            selected.length > 0 && "text-foreground"
          )}
          aria-label={
            selected.length > 0
              ? `Filter artifacts (${selected.length} active)`
              : "Filter artifacts"
          }
        >
          <FilterIcon className="size-4" />
          {selected.length > 0 ? (
            <span className="absolute top-0.5 right-0.5 size-1.5 rounded-full bg-primary" />
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-52 select-none"
      >
        <DropdownMenuLabel>Filter by type</DropdownMenuLabel>
        <DropdownMenuGroup>
          {formats.map(([format, count]) => {
            const FormatIcon = FORMAT_ICONS[format] ?? FileIcon
            return (
              <DropdownMenuCheckboxItem
                key={format}
                checked={selected.includes(format)}
                onCheckedChange={(checked) =>
                  onToggle(format, checked === true)
                }
                onSelect={(event) => event.preventDefault()} // stay open for a second pick
              >
                <FormatIcon className="size-4 text-muted-foreground" />
                <span className="flex-1">
                  {labels.get(format) ?? format}{" "}
                  <span className="text-muted-foreground">({count})</span>
                </span>
              </DropdownMenuCheckboxItem>
            )
          })}
        </DropdownMenuGroup>
        {selected.length > 0 ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onClear}>Clear filter</DropdownMenuItem>
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
  const [deleteTarget, setDeleteTarget] = useState<Artifact | null>(null)
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

  const availableFormats = useMemo(() => {
    const counts = new Map<string, number>()
    for (const artifact of artifacts) {
      counts.set(artifact.format, (counts.get(artifact.format) ?? 0) + 1)
    }
    return [...counts.entries()]
  }, [artifacts])

  // Filtered directly against what's selected, not intersected with what's
  // available — a filter saved in another workspace (e.g. "podcast") should
  // correctly show zero results here rather than silently showing everything.
  const visibleArtifacts = useMemo(() => {
    if (selectedFormats.length === 0) return artifacts
    const wanted = new Set(selectedFormats)
    return artifacts.filter((artifact) => wanted.has(artifact.format))
  }, [artifacts, selectedFormats])

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
          className="px-1 text-xs font-medium text-muted-foreground"
        >
          Artifacts
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
      <ScrollShadow className="min-h-0 flex-1" from="from-background">
        {isLoading ? (
          <SkeletonSlabs />
        ) : artifacts.length === 0 ? (
          <Empty className="min-h-0 border-0 px-2">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FileTextIcon />
              </EmptyMedia>
              <EmptyTitle>No generated artifacts yet</EmptyTitle>
              <EmptyDescription>
                Artifacts generated in Studio will appear here.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : visibleArtifacts.length === 0 ? (
          <Empty className="min-h-0 border-0 px-2">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FilterIcon />
              </EmptyMedia>
              <EmptyTitle>No artifacts match this filter</EmptyTitle>
              <EmptyDescription>
                <Button type="button" variant="link" onClick={clearFormats}>
                  Clear filter
                </Button>
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ul className="flex list-none flex-col gap-1">
            {visibleArtifacts.map((artifact) => (
              <ArtifactRow
                key={artifact.id}
                artifact={artifact}
                onOpen={() => onOpen(artifact.id)}
                onRegenerate={() => onRegenerate(artifact.id)}
                onCancel={() => onCancel(artifact.id)}
                onDelete={() => setDeleteTarget(artifact)}
              />
            ))}
          </ul>
        )}
      </ScrollShadow>
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {deleteTarget?.title ?? "this artifact"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes {deleteTarget?.title ?? "this artifact"}{" "}
              and its generated files.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleteTarget) onDelete(deleteTarget.id)
              }}
            >
              Delete artifact
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
