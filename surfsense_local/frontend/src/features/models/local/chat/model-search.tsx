import { Fragment, useEffect, useId, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { DotIcon, SearchIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import {
  HUGGINGFACE,
  destinationsQueryKey,
  listDestinations,
  setDestinationEnabled,
} from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import {
  getRepoDetail,
  searchModels,
  type LocalBuild,
  type SearchRow,
} from "./api"
import { BuildAction } from "./build-action"
import { FitBadge, FitReason } from "./fit-badge"
import { InstallProgress } from "./install-progress"
import type { InstallState } from "./use-chat-install"

// Tall enough for a handful of results, so the common search neither moves the
// page nor leaves a hole under a short list. The section is the last thing in
// the scroll region, where any change in height drags the content above it.
const RESERVED = "min-h-80"

// Matches the API side cache. Hugging Face allows 500 requests per 5 minutes,
// and a list is refetched on every keystroke a debounce lets through.
const STALE_MS = 300_000

const formatSize = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

const formatDownloads = (count: number) =>
  new Intl.NumberFormat(undefined, { notation: "compact" }).format(count)

/** What a row says about a repo, in the order it is said. */
const describe = (hit: SearchRow) => [
  `${formatDownloads(hit.downloads)} downloads`,
  ...(hit.license ? [hit.license] : []),
]

/**
 * One repo's builds, fetched when the row is opened. The listing alone: each
 * size is exact and each fit an estimate, and the one header read happens when
 * a build is installed. Search describes and never recommends.
 */
function RepoBuilds({
  repo,
  onInstall,
  onCancel,
  installState,
  disabled,
}: {
  repo: string
  onInstall: (build: LocalBuild, label: string) => void
  onCancel: () => void
  installState: InstallState
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
        Listing this model's builds
      </p>
    )
  }
  if (detail.isError || !detail.data) {
    return (
      <p className="px-3 py-2 text-xs text-destructive">
        Could not list this model's builds.
      </p>
    )
  }

  const { row } = detail.data
  if (row.builds.length === 0) {
    return (
      <p className="px-3 py-2 text-xs text-muted-foreground">
        This repo has no build SurfSense can run.
      </p>
    )
  }

  return (
    <>
      <p className="px-3 pt-2 text-xs text-muted-foreground">
        {row.runnable
          ? "Sizes are exact. Fit is estimated and checked before download."
          : row.not_runnable_reason}
      </p>
      <ul className="flex flex-col divide-y" aria-label={`Builds in ${repo}`}>
        {row.builds.map((build) => (
          <li
            key={build.catalog_id || build.quantization}
            className="flex flex-col gap-2 px-3 py-2"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {build.quantization}
                  </span>
                  <FitBadge fit={build.fit} copy={build.badge} />
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatSize(build.footprint_bytes)}
                  </span>
                </div>
                <FitReason copy={build.badge} />
              </div>
              <BuildAction
                build={build}
                label={repo}
                installState={installState}
                disabled={disabled}
                runtimeAvailable
                onAction={(target) => onInstall(target, repo)}
              />
            </div>
            {installState.status === "installing" &&
            installState.catalogId === build.catalog_id ? (
              <InstallProgress event={installState.event} onCancel={onCancel} />
            ) : null}
          </li>
        ))}
      </ul>
    </>
  )
}

export function ModelSearch({
  onInstall,
  onCancel,
  installState,
  disabled,
}: {
  onInstall: (build: LocalBuild, label: string) => void
  onCancel: () => void
  installState: InstallState
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
            The wider Hugging Face catalog, not reviewed by us. Ordered by
            downloads.
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

      {/* Reserved once, so the page does not move as the section goes from a
          prompt to a spinner to a list and back. Results scroll inside it
          rather than stretching the page, as a server's models do. */}
      <div data-slot="search-results" className={RESERVED}>
        {trimmed.length <= 1 ? (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            Type to find a model on Hugging Face.
          </p>
        ) : results.isPending ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-3" />
            Searching
          </p>
        ) : results.isError ? (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            Searching needs access to huggingface.co, which is turned off or
            unreachable. Tested models and anything already installed still
            work.
          </p>
        ) : results.data.results.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No models match &ldquo;{trimmed}&rdquo;.
          </p>
        ) : (
          <ScrollShadow
            className="overflow-hidden rounded-xl border bg-card"
            viewportClassName="max-h-80"
          >
            <ul className="divide-y" aria-label="Search results">
              {results.data.results.map((hit) => {
                const open = openRepo === hit.repo
                const parts = describe(hit)
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
                          {hit.reads_images ? (
                            <Badge variant="secondary">Vision</Badge>
                          ) : null}
                          {hit.gated ? (
                            <Badge variant="outline">Needs an account</Badge>
                          ) : null}
                        </div>
                        <p className="flex min-w-0 items-center text-xs text-muted-foreground">
                          {parts.map((part, index) => (
                            <Fragment key={part}>
                              {index > 0 ? (
                                <DotIcon
                                  aria-hidden="true"
                                  className="size-3 shrink-0"
                                />
                              ) : null}
                              {/* The tail is the longest part and the least load
                              bearing, so it is the one that ellipsizes: the
                              count and the licence stay whole at any width. */}
                              <span
                                className={
                                  index === parts.length - 1
                                    ? "min-w-0 truncate"
                                    : "shrink-0"
                                }
                              >
                                {part}
                              </span>
                            </Fragment>
                          ))}
                        </p>
                      </div>
                    </button>
                    {open ? (
                      <div className="border-t bg-muted/20">
                        <RepoBuilds
                          repo={hit.repo}
                          onInstall={onInstall}
                          onCancel={onCancel}
                          installState={installState}
                          disabled={disabled}
                        />
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </ScrollShadow>
        )}
      </div>
    </section>
  )
}
