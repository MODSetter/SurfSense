import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { FileTextIcon, Trash2Icon } from "@/components/ui/icons"

import type { Artifact } from "./api"

const statusVariant = {
  pending: "outline",
  processing: "secondary",
  ready: "secondary",
  failed: "destructive",
} as const

export function ArtifactList({
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
  return (
    <section
      className="mt-2 w-full min-w-0 overflow-hidden"
      aria-labelledby="all-artifacts"
    >
      <div className="mb-2 flex min-h-7 items-center px-1">
        <h3
          id="all-artifacts"
          className="text-xs font-medium text-muted-foreground"
        >
          All generated artifacts
        </h3>
      </div>
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
        <div className="flex flex-col gap-1.5">
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
      )}
    </section>
  )
}
