import { useState, type ComponentType } from "react"
import {
  AiSearchLinesIcon,
  Cards01Icon,
  ChartHistogramIcon,
  CheckIcon,
  File02Icon,
  FileIcon,
  Image01Icon,
  NetworkIcon,
  Pdf01Icon,
  PodcastIcon,
  Presentation02Icon,
  Quiz02Icon,
  SparklesIcon,
  WebDesign01Icon,
  Xls01Icon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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

import type { StudioFormat, StudioJobCreate } from "./api"

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

export const FORMAT_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  summary: AiSearchLinesIcon,
  docx: File02Icon,
  pptx: Presentation02Icon,
  xlsx: Xls01Icon,
  html: WebDesign01Icon,
  pdf: Pdf01Icon,
  mindmap: NetworkIcon,
  flashcards: Cards01Icon,
  quiz: Quiz02Icon,
  podcast: PodcastIcon,
  image: Image01Icon,
  infographic: ChartHistogramIcon,
}

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
  const [selected, setSelected] = useState(
    () => new Set(ready.map((document) => document.id))
  )
  const [prompt, setPrompt] = useState("")
  const allSelected = ready.length > 0 && selected.size === ready.length

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
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-muted-foreground">
            Sources ({selected.size} selected)
          </p>
          {ready.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              onClick={() =>
                setSelected(
                  allSelected
                    ? new Set()
                    : new Set(ready.map((document) => document.id))
                )
              }
            >
              {allSelected ? "Deselect all" : "Select all"}
            </Button>
          ) : null}
        </div>
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
  documents,
  formats,
  isLoading,
  isCreating,
  error,
  onGenerate,
}: {
  documents: WorkspaceDocument[]
  formats: StudioFormat[]
  isLoading: boolean
  isCreating: boolean
  error: string | null
  onGenerate: (job: StudioJobCreate) => Promise<boolean>
}) {
  const [format, setFormat] = useState<string | null>(null)
  const selectedFormat = formats.find((entry) => entry.key === format)

  return (
    <>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Studio action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? (
        <div className="grid grid-cols-3 gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((item) => (
            <Skeleton key={item} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <section className="space-y-2" aria-labelledby="studio-formats">
          <h3
            id="studio-formats"
            className="px-1 text-xs font-medium text-muted-foreground"
          >
            Studio
          </h3>
          <div className="grid grid-cols-3 gap-1.5">
            {formats.map((entry) => (
              <FormatCard
                key={entry.key}
                entry={entry}
                selected={format === entry.key}
                onSelect={() => setFormat(entry.key)}
              />
            ))}
          </div>
        </section>
      )}

      <Dialog
        open={selectedFormat != null}
        onOpenChange={(open) => {
          if (!open) setFormat(null)
        }}
      >
        <DialogContent className="p-6 select-none sm:max-w-lg [&_[data-slot=dialog-close]]:top-3 [&_[data-slot=dialog-close]]:right-3">
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
                isCreating={isCreating}
                onGenerate={(job) => {
                  void onGenerate(job).then((created) => {
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
