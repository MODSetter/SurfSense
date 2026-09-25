import { useState } from "react"
import {
  ArrowLeftIcon,
  CheckIcon,
  ChevronRightIcon,
  FileIcon,
  AiSparklesIcon,
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
import type { ModelType } from "@/features/models/model-type"
import { intl } from "@/i18n/intl"

import type { StudioFormat, StudioJobCreate } from "./api"
import { PodcastBriefForm } from "./podcast-brief-form"
import { FORMAT_ICONS, formatLabel, studioCatalog } from "./studio-formats"
import { usePodcastBrief } from "./use-podcast-brief"

const FORMAT_HINTS: Record<string, () => string> = {
  summary: () =>
    intl.formatMessage({
      id: "studio_format_summary_tooltip",
      defaultMessage: "Generate an AI summary based on your sources",
    }),
  docx: () =>
    intl.formatMessage({
      id: "studio_format_docx_tooltip",
      defaultMessage: "Generate an AI Word document based on your sources",
    }),
  pptx: () =>
    intl.formatMessage({
      id: "studio_format_pptx_tooltip",
      defaultMessage: "Generate an AI slide deck based on your sources",
    }),
  xlsx: () =>
    intl.formatMessage({
      id: "studio_format_xlsx_tooltip",
      defaultMessage: "Generate an AI spreadsheet based on your sources",
    }),
  html: () =>
    intl.formatMessage({
      id: "studio_format_html_tooltip",
      defaultMessage:
        "Generate an AI interactive web page based on your sources",
    }),
  pdf: () =>
    intl.formatMessage({
      id: "studio_format_pdf_tooltip",
      defaultMessage: "Generate an AI PDF based on your sources",
    }),
  mindmap: () =>
    intl.formatMessage({
      id: "studio_format_mindmap_tooltip",
      defaultMessage: "Generate an AI mind map based on your sources",
    }),
  flashcards: () =>
    intl.formatMessage({
      id: "studio_format_flashcards_tooltip",
      defaultMessage: "Generate AI flashcards based on your sources",
    }),
  quiz: () =>
    intl.formatMessage({
      id: "studio_format_quiz_tooltip",
      defaultMessage: "Generate an AI interactive quiz based on your sources",
    }),
  podcast: () =>
    intl.formatMessage({
      id: "studio_format_podcast_tooltip",
      defaultMessage: "Generate an AI podcast based on your sources",
    }),
  image: () =>
    intl.formatMessage({
      id: "studio_format_image_tooltip",
      defaultMessage: "Generate an AI image based on your sources",
    }),
  infographic: () =>
    intl.formatMessage({
      id: "studio_format_infographic_tooltip",
      defaultMessage: "Generate an AI infographic based on your sources",
    }),
}

function catalogFormats(formats: StudioFormat[]) {
  const catalog = studioCatalog()
  if (formats.length === 0) return catalog
  const loaded = new Map(formats.map((entry) => [entry.key, entry]))
  return catalog.map((entry) => loaded.get(entry.key) ?? entry)
}

// Only for the catalog painted before the API answers; the backend's own
// reason replaces it.
const NEEDED_MODEL: Record<ModelType, () => string> = {
  text_gen: () =>
    intl.formatMessage({
      id: "studio_format_needs_chat_model_label",
      defaultMessage: "a chat model",
    }),
  image_gen: () =>
    intl.formatMessage({
      id: "studio_format_needs_image_model_label",
      defaultMessage: "an image model",
    }),
  image_edit: () =>
    intl.formatMessage({
      id: "studio_format_needs_image_edit_model_label",
      defaultMessage: "an image editing model",
    }),
  video_gen: () =>
    intl.formatMessage({
      id: "studio_format_needs_video_model_label",
      defaultMessage: "a video model",
    }),
  audio_gen: () =>
    intl.formatMessage({
      id: "studio_format_needs_audio_model_label",
      defaultMessage: "an audio model",
    }),
}

function unavailableReason(entry: StudioFormat) {
  if (entry.unavailable_reason != null) return entry.unavailable_reason
  const models = intl.formatList(
    entry.requires_model_types.map((type) => NEEDED_MODEL[type]()),
    { type: "conjunction" }
  )
  return intl.formatMessage(
    {
      id: "studio_format_unavailable_tooltip",
      defaultMessage: "Needs {models}",
    },
    { models }
  )
}

function formatHint(entry: StudioFormat) {
  if (!entry.available) {
    return unavailableReason(entry)
  }
  return (
    FORMAT_HINTS[entry.key]?.() ??
    intl.formatMessage(
      {
        id: "studio_format_generic_tooltip",
        defaultMessage: "Generate a {format} based on your sources",
      },
      {
        format: entry.label.toLowerCase(),
      }
    )
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
                {podcast.error ??
                  intl.formatMessage({
                    id: "studio_composer_brief_status",
                    defaultMessage: "Preparing the brief…",
                  })}
              </p>
            )
          ) : null}

          {ready.length === 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                {intl.formatMessage({
                  id: "studio_composer_sources_label",
                  defaultMessage: "Sources",
                })}
              </p>
              <p className="text-sm text-muted-foreground">
                {intl.formatMessage({
                  id: "studio_composer_sources_empty",
                  defaultMessage:
                    "Add and index a source first — only ready documents can be used.",
                })}
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
                {intl.formatMessage(
                  {
                    id: "studio_composer_sources_button",
                    defaultMessage:
                      "{count, plural, one {# source} other {# sources}}",
                  },
                  {
                    count: selected.size,
                  }
                )}
              </span>
              <ChevronRightIcon className="size-4 text-muted-foreground" />
            </Button>
          )}

          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              {intl.formatMessage({
                id: "studio_composer_prompt_label",
                defaultMessage: "Prompt (optional)",
              })}
            </p>
            <Input
              className="select-text"
              value={prompt}
              placeholder={intl.formatMessage({
                id: "studio_composer_prompt_placeholder",
                defaultMessage: "Steer the focus, e.g. emphasise the risks",
              })}
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
              <AiSparklesIcon data-icon="inline-start" />
            )}
            {intl.formatMessage({
              id: "studio_composer_generate_button",
              defaultMessage: "Generate",
            })}
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
            {intl.formatMessage(
              {
                id: "studio_source_picker_back_button",
                defaultMessage: "Sources ({count, number} selected)",
              },
              {
                count: selected.size,
              }
            )}
          </button>
          {ready.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              onClick={onToggleAll}
            >
              {allSelected
                ? intl.formatMessage({
                    id: "studio_source_picker_deselect_all_button",
                    defaultMessage: "Deselect all",
                  })
                : intl.formatMessage({
                    id: "studio_source_picker_select_all_button",
                    defaultMessage: "Select all",
                  })}
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
            {formatLabel(entry)}
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
          <AlertTitle>
            {intl.formatMessage({
              id: "studio_panel_error_title",
              defaultMessage: "Studio action failed",
            })}
          </AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <section
        className="space-y-2"
        aria-label={intl.formatMessage({
          id: "studio_panel_formats_aria",
          defaultMessage: "Studio formats",
        })}
      >
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
                <DialogTitle>{formatLabel(selectedFormat)}</DialogTitle>
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
