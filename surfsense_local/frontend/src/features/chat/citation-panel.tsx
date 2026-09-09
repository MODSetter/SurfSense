import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useRef } from "react"

import { Button } from "@/components/ui/button"
import { XIcon } from "@/components/ui/icons"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { getDocumentByChunk } from "@/features/sources/api"

export function CitationPanel({
  workspaceId,
  chunkId,
  onClose,
  onOpen,
}: {
  workspaceId: number
  chunkId: number
  onClose: () => void
  onOpen: (documentId: number) => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["citation-panel", workspaceId, chunkId],
    queryFn: ({ signal }) => getDocumentByChunk(workspaceId, chunkId, signal),
    staleTime: 5 * 60 * 1000,
  })

  const cited = useMemo(
    () => data?.chunks.find((chunk) => chunk.id === chunkId) ?? null,
    [data, chunkId]
  )
  const totalChunks = data?.total_chunks ?? data?.chunks.length ?? 0
  const startIndex = data?.chunk_start_index ?? 0
  const hasMoreAbove = startIndex > 0
  const hasMoreBelow = data
    ? startIndex + data.chunks.length < totalChunks
    : false

  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const citedRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!cited) return
    const id = requestAnimationFrame(() => {
      const container = scrollContainerRef.current
      const target = citedRef.current
      if (!container || !target) return
      const offset =
        target.getBoundingClientRect().top -
        container.getBoundingClientRect().top +
        container.scrollTop
      container.scrollTo({ top: Math.max(0, offset - 16), behavior: "smooth" })
    })
    return () => cancelAnimationFrame(id)
  }, [cited])

  return (
    <aside
      className="flex h-full min-w-0 flex-col border-l bg-background"
      aria-label="Citation"
    >
      <div className="grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-3">
        <p className="min-w-0 truncate text-sm text-muted-foreground">
          {data?.title ?? (isLoading ? "Loading…" : `Chunk #${chunkId}`)}
        </p>
        <div className="flex items-center gap-1">
          {data?.document_type === "FILE" ? (
            <Button
              variant="default"
              size="sm"
              className="h-6 px-1.5 text-[11px]"
              onClick={() => onOpen(data.id)}
            >
              Open
            </Button>
          ) : null}
          <Separator
            orientation="vertical"
            className="mx-1.5 data-vertical:h-4 data-vertical:w-px"
          />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close citation"
          >
            <XIcon />
          </Button>
        </div>
      </div>

      <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {isLoading ? (
          <div className="flex min-h-full items-center justify-center text-muted-foreground">
            <Spinner />
          </div>
        ) : null}
        {error ? (
          <div className="flex min-h-full items-center justify-center text-center">
            <p className="text-sm text-destructive">
              {error instanceof Error ? error.message : "Failed to load citation"}
            </p>
          </div>
        ) : null}
        {!isLoading && !error && data ? (
          <>
            {hasMoreAbove ? (
              <p className="mb-3 text-center text-[11px] text-muted-foreground">
                … {startIndex} earlier chunk{startIndex === 1 ? "" : "s"} not
                shown
              </p>
            ) : null}
            <div className="space-y-3">
              {data.chunks.map((chunk) => {
                const isCited = chunk.id === chunkId
                return (
                  <div
                    key={chunk.id}
                    ref={isCited ? citedRef : null}
                    className={
                      isCited
                        ? "rounded-md border-2 border-primary bg-accent px-4 py-3 shadow-sm"
                        : "rounded-md bg-accent px-4 py-3 opacity-70"
                    }
                  >
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground">
                        Chunk #{chunk.id}
                      </span>
                      {isCited ? (
                        <span className="text-[11px] font-semibold text-primary">
                          Cited chunk
                        </span>
                      ) : null}
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{chunk.content}</p>
                  </div>
                )
              })}
            </div>
            {hasMoreBelow ? (
              <p className="mt-3 text-center text-[11px] text-muted-foreground">
                … {totalChunks - (startIndex + data.chunks.length)} later chunk
                {totalChunks - (startIndex + data.chunks.length) === 1
                  ? ""
                  : "s"}{" "}
                not shown
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </aside>
  )
}
