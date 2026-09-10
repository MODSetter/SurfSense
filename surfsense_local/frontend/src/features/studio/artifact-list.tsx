import { useState } from "react"
import {
  Alert02Icon,
  EllipsisIcon,
  FileIcon,
  FileTextIcon,
  Loader2Icon,
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
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import type { Artifact } from "./api"
import { FORMAT_ICONS } from "./studio-panel"

function ArtifactRow({
  artifact,
  onOpen,
  onDelete,
}: {
  artifact: Artifact
  onOpen: () => void
  onDelete: () => void
}) {
  const ready = artifact.status === "ready"
  const failed = artifact.status === "failed"
  const ingesting =
    artifact.status === "pending" || artifact.status === "processing"
  const processing = artifact.status === "processing"
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const FormatIcon = FORMAT_ICONS[artifact.format] ?? FileIcon

  return (
    <div
      className={cn(
        "group group/artifact relative flex h-8 w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 hover:bg-muted dark:hover:bg-muted/50",
        dropdownOpen && "bg-muted dark:bg-muted/50"
      )}
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
        {failed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={artifact.error_message ?? "Generation failed"}
                className="hover:bg-transparent"
              >
                <Alert02Icon className="size-4.5 text-destructive" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left" collisionPadding={8}>
              {artifact.error_message ?? "Generation failed"}
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
          <DropdownMenuContent align="end" sideOffset={8} className="min-w-40">
            <DropdownMenuGroup>
              {ready ? (
                <DropdownMenuItem onSelect={onOpen}>
                  <ViewIcon />
                  Open
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
    </div>
  )
}

export function ArtifactList({
  artifacts,
  onOpen,
  onDelete,
}: {
  artifacts: Artifact[]
  onOpen: (id: number) => void
  onDelete: (id: number) => void
}) {
  const [deleteTarget, setDeleteTarget] = useState<Artifact | null>(null)

  return (
    <section
      className="flex h-full min-h-0 w-full min-w-0 flex-col"
      aria-labelledby="all-artifacts"
    >
      <div className="mb-2 flex min-h-7 shrink-0 items-center px-1">
        <h3
          id="all-artifacts"
          className="text-xs font-medium text-muted-foreground"
        >
          All generated artifacts
        </h3>
      </div>
      <ScrollShadow className="min-h-0 flex-1" from="from-background">
        {artifacts.length === 0 ? (
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
        ) : (
          <div className="flex flex-col gap-1">
            {artifacts.map((artifact) => (
              <ArtifactRow
                key={artifact.id}
                artifact={artifact}
                onOpen={() => onOpen(artifact.id)}
                onDelete={() => setDeleteTarget(artifact)}
              />
            ))}
          </div>
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
              This permanently deletes{" "}
              {deleteTarget?.title ?? "this artifact"} and its generated files.
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
