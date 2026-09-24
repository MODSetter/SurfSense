import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useRef } from "react"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import { Spinner } from "@/components/ui/spinner"
import { getDocumentByChunk } from "@/features/sources/api"
import { intl } from "@/i18n/intl"

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
    <DetailPanel
      title={
        data?.title ??
        (isLoading
          ? intl.formatMessage({
              id: "chat_citation_panel_loading_status",
              defaultMessage: "Loading…",
            })
          : intl.formatMessage(
              {
                id: "chat_citation_panel_chunk_title",
                defaultMessage: "Chunk #{id}",
              },
              { id: chunkId }
            ))
      }
      ariaLabel={intl.formatMessage({
        id: "chat_citation_panel_aria",
        defaultMessage: "Citation",
      })}
      closeLabel={intl.formatMessage({
        id: "chat_citation_panel_close_aria",
        defaultMessage: "Close citation",
      })}
      onClose={onClose}
      bodyRef={scrollContainerRef}
      actions={
        data?.document_type === "FILE" ? (
          <Button
            variant="default"
            size="sm"
            className="h-6 px-1.5 text-[11px]"
            onClick={() => onOpen(data.id)}
          >
            {intl.formatMessage({
              id: "chat_citation_panel_open_file_button",
              defaultMessage: "Open file",
            })}
          </Button>
        ) : null
      }
    >
      {isLoading ? (
        <div className="flex min-h-full items-center justify-center text-muted-foreground">
          <Spinner />
        </div>
      ) : null}
      {error ? (
        <div className="flex min-h-full items-center justify-center text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error
              ? error.message
              : intl.formatMessage({
                  id: "chat_citation_panel_load_error",
                  defaultMessage: "Failed to load citation",
                })}
          </p>
        </div>
      ) : null}
      {!isLoading && !error && data ? (
        <>
          {hasMoreAbove ? (
            <p className="mb-3 text-center text-[11px] text-muted-foreground">
              {intl.formatMessage(
                {
                  id: "chat_citation_panel_earlier_chunks_body",
                  defaultMessage:
                    "… {count, plural, one {# earlier chunk} other {# earlier chunks}} not shown",
                },
                {
                  count: startIndex,
                }
              )}
            </p>
          ) : null}
          <div className="flex flex-col gap-3">
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
                      {intl.formatMessage(
                        {
                          id: "chat_citation_panel_chunk_label",
                          defaultMessage: "Chunk #{id}",
                        },
                        {
                          id: chunk.id,
                        }
                      )}
                    </span>
                    {isCited ? (
                      <span className="text-[11px] font-semibold text-primary">
                        {intl.formatMessage({
                          id: "chat_citation_panel_cited_label",
                          defaultMessage: "Cited chunk",
                        })}
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
              {intl.formatMessage(
                {
                  id: "chat_citation_panel_later_chunks_body",
                  defaultMessage:
                    "… {count, plural, one {# later chunk} other {# later chunks}} not shown",
                },
                {
                  count: totalChunks - (startIndex + data.chunks.length),
                }
              )}
            </p>
          ) : null}
        </>
      ) : null}
    </DetailPanel>
  )
}
