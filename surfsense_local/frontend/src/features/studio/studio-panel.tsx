import { useState } from "react"
import {
  ArrowLeftIcon,
  CheckIcon,
  ChevronRightIcon,
  FileIcon,
  SparklesIcon,
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
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

import type { StudioFormat, StudioJobCreate } from "./api"
import { PodcastBriefForm } from "./podcast-brief-form"
import { FORMAT_ICONS, STUDIO_CATALOG } from "./studio-formats"
import { usePodcastBrief } from "./use-podcast-brief"

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

function catalogFormats(formats: StudioFormat[]) {
  if (formats.length === 0) return STUDIO_CATALOG
  const loaded = new Map(formats.map((entry) => [entry.key, entry]))
  return STUDIO_CATALOG.map((entry) => loaded.get(entry.key) ?? entry)
}

function unavailableReason(entry: StudioFormat) {
  return (
    entry.unavailable_reason ??
    `Needs a ${entry.requires_roles.join(" and ").replaceAll("_", " ")} model`
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
  workspaceId,
  format,
  documents,
  selectedDocumentIds,
  onSelectionChange,
  onToggleAll,
  isCreating,
  onGenerate,
}: {
  workspaceId: number
  format: string
  documents: WorkspaceDocument[]
  selectedDocumentIds: number[]
  onSelectionChange: (documentId: number, included: boolean) => void
  onToggleAll: () => void
  isCreating: boolean
  onGenerate: (job: StudioJobCreate) => void
}) {
  const ready = documents.filter((document) => document.status === "ready")
  const selected = new Set(selectedDocumentIds)
  const [prompt, setPrompt] = useState("")
  const [view, setView] = useState<"main" | "sources">("main")
  const podcast = usePodcastBrief(format === "podcast" ? workspaceId : null)
  const allSelected = ready.length > 0 && selected.size === ready.length

  const toggle = (id: number) => onSelectionChange(id, !selected.has(id))

  // A podcast is generated from its reviewed brief, so it waits for the brief.
  const briefReady = format !== "podcast" || podcast.brief != null
  const canGenerate = selected.size > 0 && !isCreating && briefReady

  return (
    <div className="relative">
      <div
        className={cn(
          "flex flex-col transition-[opacity,filter] duration-250 ease-out motion-reduce:transition-none",
          view === "main"
            ? "opacity-100 blur-none"
            : "pointer-events-none invisible opacity-0 blur-sm"
        )}
        aria-hidden={view !== "main"}
      >
        <div className="space-y-3">
          {format === "podcast" ? (
            podcast.brief ? (
              <PodcastBriefForm
                brief={podcast.brief}
                voices={podcast.voices}
                onChange={podcast.setBrief}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                {podcast.error ?? "Preparing the brief…"}
              </p>
            )
          ) : null}

          {ready.length === 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Sources
              </p>
              <p className="text-sm text-muted-foreground">
                Add and index a source first — only ready documents can be
                used.
              </p>
            </div>
          ) : (
            <Button
              type="button"
              variant="secondary"
              onClick={() => setView("sources")}
              className="h-10 w-full justify-between px-2.5 font-normal"
            >
              <span className="min-w-0 flex-1 truncate text-left">
                {selected.size} source{selected.size === 1 ? "" : "s"}
              </span>
              <ChevronRightIcon className="size-4 text-muted-foreground" />
            </Button>
          )}

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
        </div>

        <div className="mt-auto pt-3">
          <Button
            className="w-full"
            disabled={!canGenerate}
            onClick={() => {
              onGenerate({
                format,
                document_ids: [...selected],
                prompt: prompt.trim() || undefined,
                options: podcast.brief ?? undefined,
              })
            }}
          >
            {isCreating ? (
              <Spinner />
            ) : (
              <SparklesIcon data-icon="inline-start" />
            )}
            Generate
          </Button>
        </div>
      </div>

      <div
        className={cn(
          "absolute inset-0 flex flex-col gap-2 transition-[opacity,filter] duration-250 ease-out motion-reduce:transition-none",
          view === "sources"
            ? "opacity-100 blur-none"
            : "pointer-events-none invisible opacity-0 blur-sm"
        )}
        aria-hidden={view !== "sources"}
      >
        <div className="flex shrink-0 items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setView("main")}
            className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeftIcon className="size-3.5" />
            Sources ({selected.size} selected)
          </button>
          {ready.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              onClick={onToggleAll}
            >
              {allSelected ? "Deselect all" : "Select all"}
            </Button>
          ) : null}
        </div>
        <ScrollShadow className="min-h-0 flex-1" viewportClassName="pr-2">
          <div className="space-y-1">
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
        </ScrollShadow>
      </div>
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
            "flex min-w-0 cursor-pointer flex-col items-center gap-1 rounded-lg border border-transparent bg-muted/40 px-1 py-2 text-center [&_svg]:size-4",
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
  selectedDocumentIds,
  onSelectionChange,
  onToggleAll,
  formats,
  isCreating,
  error,
  onGenerate,
}: {
  workspaceId: number
  documents: WorkspaceDocument[]
  selectedDocumentIds: number[]
  onSelectionChange: (documentId: number, included: boolean) => void
  onToggleAll: () => void
  formats: StudioFormat[]
  isCreating: boolean
  error: string | null
  onGenerate: (job: StudioJobCreate) => Promise<boolean>
}) {
  const [format, setFormat] = useState<string | null>(null)
  const catalog = catalogFormats(formats)
  const selectedFormat = catalog.find((entry) => entry.key === format)

  return (
    <>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Studio action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <section className="space-y-2" aria-label="Studio formats">
        <div className="grid grid-cols-3 gap-1.5">
          {catalog.map((entry) => (
            <FormatCard
              key={entry.key}
              entry={entry}
              selected={format === entry.key}
              onSelect={() => setFormat(entry.key)}
            />
          ))}
        </div>
      </section>

      <Dialog
        open={selectedFormat != null}
        onOpenChange={(open) => {
          if (!open) setFormat(null)
        }}
      >
        <DialogContent className="p-6 select-none **:data-[slot=dialog-close]:top-3 **:data-[slot=dialog-close]:right-3 sm:max-w-lg">
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
                workspaceId={workspaceId}
                format={selectedFormat.key}
                documents={documents}
                selectedDocumentIds={selectedDocumentIds}
                onSelectionChange={onSelectionChange}
                onToggleAll={onToggleAll}
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
