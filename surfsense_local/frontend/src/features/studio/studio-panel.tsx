import { useState, type ComponentType } from "react"
import {
  BrowserIcon,
  Cards01Icon,
  ChartHistogramIcon,
  CheckIcon,
  File02Icon,
  FileIcon,
  FileTextIcon,
  HierarchyIcon,
  Image01Icon,
  Pdf01Icon,
  PodcastIcon,
  Presentation01Icon,
  Quiz01Icon,
  SparklesIcon,
  Trash2Icon,
  Xls01Icon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

import type { Artifact, StudioFormat } from "./api"
import { useStudio } from "./use-studio"

const FORMAT_HINTS: Record<string, string> = {
  summary: "Generate an AI summary based on your sources",
  docx: "Generate an AI Word document based on your sources",
  pptx: "Generate an AI slide deck based on your sources",
  xlsx: "Generate an AI spreadsheet based on your sources",
  html: "Generate an AI interactive web page based on your sources",
  pdf: "Generate an AI PDF based on your sources",
  mindmap: "Generate an AI mind map based on your sources",
  flashcards: "Generate AI flashcards based on your sources",
  quiz: "Generate an AI interactive quiz based on your sources",
  podcast: "Generate an AI podcast based on your sources",
  image: "Generate an AI image based on your sources",
  infographic: "Generate an AI infographic based on your sources",
}

const FORMAT_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  summary: FileTextIcon,
  docx: File02Icon,
  pptx: Presentation01Icon,
  xlsx: Xls01Icon,
  html: BrowserIcon,
  pdf: Pdf01Icon,
  mindmap: HierarchyIcon,
  flashcards: Cards01Icon,
  quiz: Quiz01Icon,
  podcast: PodcastIcon,
  image: Image01Icon,
  infographic: ChartHistogramIcon,
}

const statusVariant = {
  pending: "outline",
  processing: "secondary",
  ready: "secondary",
  failed: "destructive",
} as const

function unavailableReason(entry: StudioFormat) {
  return (
    entry.unavailable_reason ??
    `Needs a ${entry.requires_role?.replace("_", " ")} model`
  )
}

function formatHint(entry: StudioFormat) {
  if (!entry.available) {
    return unavailableReason(entry)
  }
  return (
    FORMAT_HINTS[entry.key] ??
    `Generate a ${entry.label.toLowerCase()} based on your sources`
  )
}

function Composer({
  format,
  documents,
  isCreating,
  onGenerate,
}: {
  format: string
  documents: WorkspaceDocument[]
  isCreating: boolean
  onGenerate: (job: {
    format: string
    document_ids: number[]
    prompt?: string
  }) => void
}) {
  const ready = documents.filter((document) => document.status === "ready")
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [prompt, setPrompt] = useState("")

  const toggle = (id: number) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })

  const canGenerate = selected.size > 0 && !isCreating

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">
          Sources ({selected.size} selected)
        </p>
        {ready.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Add and index a source first — only ready documents can be used.
          </p>
        ) : (
          <ScrollArea className="max-h-40">
            <div className="space-y-1 pr-2">
              {ready.map((document) => {
                const on = selected.has(document.id)
                return (
                  <button
                    key={document.id}
                    type="button"
                    onClick={() => toggle(document.id)}
                    className={cn(
                      "flex w-full cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm",
                      on ? "border-primary bg-primary/5" : "hover:bg-accent"
                    )}
                  >
                    <span
                      className={cn(
                        "flex size-4 items-center justify-center rounded border",
                        on
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/40"
                      )}
                    >
                      {on ? <CheckIcon className="size-3" /> : null}
                    </span>
                    <span className="min-w-0 flex-1 truncate">
                      {document.title}
                    </span>
                  </button>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">
          Prompt (optional)
        </p>
        <Input
          className="select-text"
          value={prompt}
          placeholder="Steer the focus, e.g. emphasise the risks"
          onChange={(event) => setPrompt(event.target.value)}
        />
      </div>

      <Button
        className="w-full"
        disabled={!canGenerate}
        onClick={() => {
          onGenerate({
            format,
            document_ids: [...selected],
            prompt: prompt.trim() || undefined,
          })
        }}
      >
        {isCreating ? <Spinner /> : <SparklesIcon data-icon="inline-start" />}
        Generate
      </Button>
    </div>
  )
}

function Library({
  artifacts,
  labelOf,
  onOpen,
  onDelete,
}: {
  artifacts: Artifact[]
  labelOf: (format: string) => string
  onOpen: (id: number) => void
  onDelete: (id: number) => void
}) {
  if (artifacts.length === 0) {
    return null
  }
  return (
    <section className="space-y-2" aria-labelledby="generated-artifacts">
      <h3
        id="generated-artifacts"
        className="px-1 text-xs font-medium text-muted-foreground"
      >
        Generated artifacts
      </h3>
      <div className="space-y-1.5">
        {artifacts.map((artifact) => (
          <div
            key={artifact.id}
            className="flex items-start gap-2 rounded-md border p-2"
          >
            <div className="min-w-0 flex-1">
              <button
                type="button"
                disabled={artifact.status !== "ready"}
                onClick={() => onOpen(artifact.id)}
                className="w-full cursor-pointer text-left disabled:cursor-default"
              >
                <span className="block truncate text-sm font-medium">
                  {artifact.title}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {labelOf(artifact.format)}
                </span>
              </button>
              {artifact.status === "failed" && artifact.error_message ? (
                <p className="mt-1 text-[11px] text-pretty text-destructive">
                  {artifact.error_message}
                </p>
              ) : null}
            </div>
            <Badge
              variant={statusVariant[artifact.status]}
              className="mt-0.5 h-4 shrink-0 px-1.5 text-[10px]"
            >
              {artifact.status}
            </Badge>
            <Button
              variant="ghost"
              size="icon-sm"
              className="shrink-0"
              aria-label={`Delete ${artifact.title}`}
              onClick={() => onDelete(artifact.id)}
            >
              <Trash2Icon />
            </Button>
          </div>
        ))}
      </div>
    </section>
  )
}

function FormatCard({
  entry,
  selected,
  onSelect,
}: {
  entry: StudioFormat
  selected: boolean
  onSelect: () => void
}) {
  const Icon = FORMAT_ICONS[entry.key] ?? FileIcon
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-disabled={!entry.available || undefined}
          aria-pressed={entry.available ? selected : undefined}
          className={cn(
            "flex min-w-0 cursor-pointer flex-col items-center gap-1 rounded-lg border bg-muted/40 px-1 py-2 text-center [&_svg]:size-4",
            entry.available
              ? "hover:bg-accent"
              : "cursor-not-allowed opacity-50",
            selected && "border-primary bg-primary/5"
          )}
          onClick={entry.available ? onSelect : undefined}
        >
          <Icon />
          <span className="w-full truncate text-[11px] leading-4">
            {entry.label}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{formatHint(entry)}</TooltipContent>
    </Tooltip>
  )
}

export function StudioPanel({
  workspaceId,
  documents,
  onOpen,
}: {
  workspaceId: number
  documents: WorkspaceDocument[]
  onOpen: (artifactId: number) => void
}) {
  const studio = useStudio(workspaceId)
  const [format, setFormat] = useState<string | null>(null)
  const selectedFormat = studio.formats.find((entry) => entry.key === format)
  const labelOf = (key: string) =>
    studio.formats.find((entry) => entry.key === key)?.label ?? key

  return (
    <>
      {studio.error ? (
        <Alert variant="destructive">
          <AlertTitle>Studio action failed</AlertTitle>
          <AlertDescription>{studio.error}</AlertDescription>
        </Alert>
      ) : null}

      {studio.isLoading ? (
        <div className="grid grid-cols-3 gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((item) => (
            <Skeleton key={item} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Library
            artifacts={studio.artifacts}
            labelOf={labelOf}
            onOpen={onOpen}
            onDelete={(id) => void studio.remove(id)}
          />
          <section className="space-y-2" aria-labelledby="studio-formats">
            <h3
              id="studio-formats"
              className="px-1 text-xs font-medium text-muted-foreground"
            >
              Studio
            </h3>
            <div className="grid grid-cols-3 gap-1.5">
              {studio.formats.map((entry) => (
                <FormatCard
                  key={entry.key}
                  entry={entry}
                  selected={format === entry.key}
                  onSelect={() => setFormat(entry.key)}
                />
              ))}
            </div>
          </section>
        </div>
      )}

      <Dialog
        open={selectedFormat != null}
        onOpenChange={(open) => {
          if (!open) setFormat(null)
        }}
      >
        <DialogContent className="select-none sm:max-w-md">
          {selectedFormat ? (
            <>
              <DialogHeader>
                <DialogTitle>{selectedFormat.label}</DialogTitle>
                <DialogDescription className="sr-only">
                  {formatHint(selectedFormat)}
                </DialogDescription>
              </DialogHeader>
              <Composer
                key={selectedFormat.key}
                format={selectedFormat.key}
                documents={documents}
                isCreating={studio.isCreating}
                onGenerate={(job) => {
                  void studio.create(job).then((created) => {
                    if (created) setFormat(null)
                  })
                }}
              />
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}
