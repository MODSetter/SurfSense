import { useState } from "react"
import {
  ArrowLeftIcon,
  CheckIcon,
  DownloadIcon,
  SparklesIcon,
  Trash2Icon,
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
  DialogTrigger,
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

import { fileUrl, type Artifact, type ArtifactDetail } from "./api"
import { useStudio } from "./use-studio"

const statusVariant = {
  pending: "outline",
  processing: "secondary",
  ready: "secondary",
  failed: "destructive",
} as const

function Composer({
  documents,
  formats,
  isCreating,
  onGenerate,
}: {
  documents: WorkspaceDocument[]
  formats: ReturnType<typeof useStudio>["formats"]
  isCreating: boolean
  onGenerate: (job: {
    format: string
    document_ids: number[]
    prompt?: string
  }) => void
}) {
  const ready = documents.filter((document) => document.status === "ready")
  const [format, setFormat] = useState<string | null>(null)
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

  const canGenerate = format !== null && selected.size > 0 && !isCreating

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Format</p>
        <div className="flex flex-wrap gap-2">
          {formats.map((entry) => {
            const unavailableReason =
              entry.unavailable_reason ??
              `Needs a ${entry.requires_role?.replace("_", " ")} model`
            return entry.available ? (
              <Button
                key={entry.key}
                type="button"
                size="sm"
                variant={format === entry.key ? "default" : "outline"}
                onClick={() => setFormat(entry.key)}
              >
                {entry.label}
              </Button>
            ) : (
              <Tooltip key={entry.key}>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    aria-disabled="true"
                    className="cursor-not-allowed opacity-50"
                  >
                    {entry.label}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">{unavailableReason}</TooltipContent>
              </Tooltip>
            )
          })}
        </div>
      </div>

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
          value={prompt}
          placeholder="Steer the focus, e.g. emphasise the risks"
          onChange={(event) => setPrompt(event.target.value)}
        />
      </div>

      <Button
        className="w-full"
        disabled={!canGenerate}
        onClick={() => {
          if (format === null) return
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
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">Artifacts</p>
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
    </div>
  )
}

function Viewer({
  artifact,
  onBack,
}: {
  artifact: ArtifactDetail
  onBack: () => void
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Back"
          onClick={onBack}
        >
          <ArrowLeftIcon />
        </Button>
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium">
          {artifact.title}
        </h3>
        {artifact.files.map((file) => (
          <Button key={file.role} size="xs" variant="outline" asChild>
            <a href={fileUrl(artifact.id, file.role)} download>
              <DownloadIcon data-icon="inline-start" />
              {file.role}
            </a>
          </Button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border">
        <Preview artifact={artifact} />
        <div className="prose prose-sm max-w-none p-4 text-sm leading-6 whitespace-pre-wrap">
          {artifact.content || "This artifact has no text body."}
        </div>
      </div>
    </div>
  )
}

// Play audio and show images inline; other files stay download-only above.
function Preview({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  if (!primary) return null

  const src = fileUrl(artifact.id, primary.role)
  if (primary.mime_type.startsWith("audio/")) {
    // biome-ignore lint/a11y/useMediaCaption: The generated transcript is rendered directly below the player.
    return <audio className="w-full p-4" controls src={src} />
  }
  if (primary.mime_type.startsWith("image/")) {
    return (
      <img className="mx-auto max-w-full p-4" alt={artifact.title} src={src} />
    )
  }
  return null
}

export function StudioDialog({
  workspaceId,
  documents,
}: {
  workspaceId: number
  documents: WorkspaceDocument[]
}) {
  const [open, setOpen] = useState(false)
  const studio = useStudio(workspaceId, open)
  const labelOf = (format: string) =>
    studio.formats.find((entry) => entry.key === format)?.label ?? format

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <SparklesIcon />
          Studio
        </Button>
      </DialogTrigger>
      <DialogContent className="flex max-h-[85svh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Studio</DialogTitle>
          <DialogDescription>
            Turn this workspace's sources into a deliverable.
          </DialogDescription>
        </DialogHeader>

        {studio.error ? (
          <Alert variant="destructive">
            <AlertTitle>Studio action failed</AlertTitle>
            <AlertDescription>{studio.error}</AlertDescription>
          </Alert>
        ) : null}

        {studio.selected ? (
          <Viewer artifact={studio.selected} onBack={studio.closeArtifact} />
        ) : studio.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="space-y-5 pr-1 pb-1">
              <Composer
                documents={documents}
                formats={studio.formats}
                isCreating={studio.isCreating}
                onGenerate={(job) => void studio.create(job)}
              />
              <Library
                artifacts={studio.artifacts}
                labelOf={labelOf}
                onOpen={(id) => void studio.openArtifact(id)}
                onDelete={(id) => void studio.remove(id)}
              />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
