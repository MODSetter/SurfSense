import { useEffect, useId, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SearchIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import {
  HUGGINGFACE,
  destinationsQueryKey,
  listDestinations,
  setDestinationEnabled,
} from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { getRepoDetail, searchModels, type RepoBuild } from "./api"
import { FitBadge, FitReason } from "./fit-badge"

// Matches the API side cache. Hugging Face allows 500 requests per 5 minutes,
// and a list is refetched on every keystroke a debounce lets through.
const STALE_MS = 300_000

const formatSize = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

const formatDownloads = (count: number) =>
  new Intl.NumberFormat(undefined, { notation: "compact" }).format(count)

/**
 * One repo's builds, fetched when the row is opened rather than when it is
 * listed: pricing a build exactly means reading two to four megabytes of its
 * header, which is not something to do for every result in a list.
 */
function RepoBuilds({
  repo,
  onInstall,
  disabled,
}: {
  repo: string
  onInstall: (build: RepoBuild) => void
  disabled: boolean
}) {
  const detail = useQuery({
    queryKey: ["llm", "search", repo],
    queryFn: ({ signal }) => getRepoDetail(repo, signal),
    staleTime: STALE_MS,
  })

  if (detail.isPending) {
    return (
      <p className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
        <Spinner className="size-3" />
        Reading this model's details
      </p>
    )
  }
  if (detail.isError || !detail.data) {
    return (
      <p className="px-3 py-2 text-xs text-destructive">
        Could not read this model's details.
      </p>
    )
  }
  if (!detail.data.supported) {
    return (
      <p className="px-3 py-2 text-xs text-muted-foreground">
        {detail.data.ineligible_reason ?? "This model cannot run here."}
      </p>
    )
  }

  return (
    <>
      {!detail.data.chat_template && (
        <p className="px-3 pt-2 text-xs text-muted-foreground">
          No chat template. It may answer badly in a chat.
        </p>
      )}
      <ul className="flex flex-col divide-y" aria-label={`Builds in ${repo}`}>
        {detail.data.builds.map((build) => (
          <li
            key={build.catalog_id}
            className="flex items-center justify-between gap-3 px-3 py-2"
          >
            <div className="flex min-w-0 flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {build.quantization}
                </span>
                <FitBadge fit={build.fit} copy={build.badge} />
                <span className="text-xs text-muted-foreground">
                  {formatSize(build.size_bytes)}
                </span>
              </div>
              <FitReason copy={build.badge} />
            </div>
            <Button
              type="button"
              size="sm"
              disabled={disabled || !build.can_install}
              onClick={() => onInstall(build)}
            >
              Download
            </Button>
          </li>
        ))}
      </ul>
    </>
  )
}

export function ModelSearch({
  onInstall,
  disabled,
}: {
  onInstall: (build: RepoBuild) => void
  disabled: boolean
}) {
  const headingId = useId()
  const [query, setQuery] = useState("")
  const [openRepo, setOpenRepo] = useState<string | null>(null)
  const trimmed = query.trim()

  const destinations = useQuery({
    queryKey: destinationsQueryKey,
    queryFn: ({ signal }) => listDestinations(signal),
  })
  const huggingface = destinations.data?.find(
    (row) => row.destination === HUGGINGFACE
  )
  // Reaching for the box is what raises the question, and it is raised as soon
  // as both are true: the user wants to search, and the answer is known to be
  // no. Either can arrive first, so neither is the trigger on its own.
  const [reached, setReached] = useState(false)
  // Once per visit. Asking again on every click is nagging, and a refusal
  // still leaves the box usable enough to read why nothing comes back.
  const asked = useRef(false)

  useEffect(() => {
    if (!reached || asked.current || huggingface === undefined) return
    if (huggingface.enabled) return
    asked.current = true
    void askEgress({
      destination: huggingface.destination,
      host: huggingface.host,
      allow: () => setDestinationEnabled(huggingface.destination, true),
    })
  }, [reached, huggingface])

  const results = useQuery({
    queryKey: ["llm", "search", "list", trimmed],
    queryFn: ({ signal }) => searchModels(trimmed, signal),
    enabled: trimmed.length > 1,
    staleTime: STALE_MS,
  })

  return (
    <section className="flex flex-col gap-2.5" aria-labelledby={headingId}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id={headingId} className="font-heading text-sm font-medium">
            All models
          </h2>
          <p className="text-xs text-muted-foreground">
            Every model llama.cpp can run. Ordered by how often each one is
            downloaded, which is popularity and not a recommendation.
          </p>
        </div>
        <div className="relative w-full max-w-[14rem] sm:w-auto">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={query}
            placeholder="Search all models"
            aria-label="Search all models"
            className="h-8 border-0 bg-secondary pl-8 text-sm focus-visible:border-0"
            onFocus={() => setReached(true)}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      {trimmed.length <= 1 ? (
        <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Type to search every model llama.cpp can run.
        </p>
      ) : results.isPending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-3" />
          Searching
        </p>
      ) : results.isError ? (
        <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Searching needs access to huggingface.co, which is turned off or
          unreachable. Tested models and anything already installed still work.
        </p>
      ) : results.data.results.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No models match &ldquo;{trimmed}&rdquo;.
        </p>
      ) : (
        <ul
          className="divide-y overflow-hidden rounded-xl border bg-card"
          aria-label="Search results"
        >
          {results.data.results.map((hit) => {
            const open = openRepo === hit.repo
            return (
              <li key={hit.repo}>
                <button
                  type="button"
                  aria-expanded={open}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/20"
                  onClick={() => setOpenRepo(open ? null : hit.repo)}
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {hit.repo}
                      </span>
                      {hit.gated ? (
                        <Badge variant="outline">Needs an account</Badge>
                      ) : null}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {formatDownloads(hit.downloads)} downloads
                      {hit.license ? ` · ${hit.license}` : ""}
                      {hit.quantized_from
                        ? ` · quantized from ${hit.quantized_from}`
                        : ""}
                    </p>
                  </div>
                </button>
                {open ? (
                  <div className="border-t bg-muted/20">
                    <RepoBuilds
                      repo={hit.repo}
                      onInstall={onInstall}
                      disabled={disabled}
                    />
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
