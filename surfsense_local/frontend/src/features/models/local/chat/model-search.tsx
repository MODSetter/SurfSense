import { Fragment, useEffect, useId, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { DotIcon, SearchIcon, XIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import {
  HUGGINGFACE,
  destinationsQueryKey,
  listDestinations,
  setDestinationEnabled,
} from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { intl } from "@/i18n/intl"
import {
  getRepoDetail,
  searchModels,
  type LocalBuild,
  type SearchRow,
} from "./api"
import { BuildAction } from "./build-action"
import { FitBadge, FitReason } from "./fit-badge"
import { InstallProgress } from "./install-progress"
import type { InstallJob } from "../installs/api"
import { jobFor } from "../installs/job-state"

// Tall enough for a handful of results, so the common search neither moves the
// page nor leaves a hole under a short list. The section is the last thing in
// the scroll region, where any change in height drags the content above it.
const RESERVED = "min-h-80"

// Matches the API side cache. Hugging Face allows 500 requests per 5 minutes,
// and a list is refetched on every keystroke a debounce lets through.
const STALE_MS = 300_000

const formatSize = (bytes: number) =>
  intl.formatNumber(bytes / 1e9, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  })

/** What a row says about a repo, in the order it is said. */
const describe = (hit: SearchRow) => [
  intl.formatMessage(
    {
      id: "models_search_downloads_label",
      defaultMessage:
        "{downloads, plural, one {{downloads, number, ::compact-short} download} other {{downloads, number, ::compact-short} downloads}}",
    },
    { downloads: hit.downloads }
  ),
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
  installs,
  disabled,
}: {
  repo: string
  onInstall: (build: LocalBuild) => void
  onCancel: (jobId: string) => void
  installs: readonly InstallJob[]
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
        {intl.formatMessage({
          id: "models_search_builds_loading_status",
          defaultMessage: "Listing this model’s builds",
        })}
      </p>
    )
  }
  if (detail.isError || !detail.data) {
    return (
      <p className="px-3 py-2 text-xs text-destructive">
        {intl.formatMessage({
          id: "models_search_builds_error",
          defaultMessage: "Could not list this model’s builds.",
        })}
      </p>
    )
  }

  const { row } = detail.data
  if (row.builds.length === 0) {
    return (
      <p className="px-3 py-2 text-xs text-muted-foreground">
        {intl.formatMessage({
          id: "models_search_builds_empty",
          defaultMessage: "This repo has no build SurfSense can run.",
        })}
      </p>
    )
  }

  return (
    <>
      <p className="px-3 pt-2 text-xs text-muted-foreground">
        {row.runnable
          ? intl.formatMessage({
              id: "models_search_builds_body",
              defaultMessage:
                "Sizes are exact. Fit is estimated and checked before download.",
            })
          : row.not_runnable_reason}
      </p>
      <ul
        className="flex flex-col divide-y"
        aria-label={intl.formatMessage(
          {
            id: "models_search_builds_aria",
            defaultMessage: "Builds in {repo}",
          },
          { repo }
        )}
      >
        {row.builds.map((build) => {
          const job = jobFor(installs, build.catalog_id)
          return (
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
                  installs={installs}
                  disabled={disabled}
                  runtimeAvailable
                  onAction={onInstall}
                />
              </div>
              {job ? (
                <InstallProgress
                  event={job.event}
                  onCancel={() => onCancel(job.id)}
                />
              ) : null}
            </li>
          )
        })}
      </ul>
    </>
  )
}

export function ModelSearch({
  onInstall,
  onCancel,
  installs,
  disabled,
  autoFocus = false,
}: {
  onInstall: (build: LocalBuild) => void
  onCancel: (jobId: string) => void
  installs: readonly InstallJob[]
  disabled: boolean
  /** Only where the search was just asked for; a page that merely lists it
   *  must not focus it, since focusing raises the egress question. */
  autoFocus?: boolean
}) {
  const headingId = useId()
  const [query, setQuery] = useState("")
  const searchRef = useRef<HTMLInputElement>(null)
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
            {intl.formatMessage({
              id: "models_search_title",
              defaultMessage: "All models",
            })}
          </h2>
          <p className="text-xs text-muted-foreground">
            {intl.formatMessage({
              id: "models_search_body",
              defaultMessage:
                "The wider Hugging Face catalog, not reviewed by us. Ordered by downloads.",
            })}
          </p>
        </div>
        <InputGroup className="w-full sm:w-56">
          <InputGroupAddon>
            <SearchIcon />
          </InputGroupAddon>
          <InputGroupInput
            ref={searchRef}
            type="search"
            autoFocus={autoFocus}
            value={query}
            placeholder={intl.formatMessage({
              id: "models_search_placeholder",
              defaultMessage: "Search all models",
            })}
            aria-label={intl.formatMessage({
              id: "models_search_aria",
              defaultMessage: "Search all models",
            })}
            // The clear button below replaces the browser's own.
            className="text-sm [&::-webkit-search-cancel-button]:appearance-none"
            onFocus={() => setReached(true)}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query ? (
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                size="icon-xs"
                aria-label={intl.formatMessage({
                  id: "models_search_clear_aria",
                  defaultMessage: "Clear search",
                })}
                onClick={() => {
                  setQuery("")
                  searchRef.current?.focus()
                }}
              >
                <XIcon />
              </InputGroupButton>
            </InputGroupAddon>
          ) : null}
        </InputGroup>
      </div>

      {/* Reserved once, so the page does not move as the section goes from a
          prompt to a spinner to a list and back. Results scroll inside it
          rather than stretching the page, as a server's models do. */}
      <div data-slot="search-results" className={RESERVED}>
        {trimmed.length <= 1 ? (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "models_search_prompt_empty",
              defaultMessage: "Type to find a model on Hugging Face.",
            })}
          </p>
        ) : results.isPending ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-3" />
            {intl.formatMessage({
              id: "models_search_searching_status",
              defaultMessage: "Searching",
            })}
          </p>
        ) : results.isError ? (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "models_search_unreachable_error",
              defaultMessage:
                "Searching needs access to huggingface.co, which is turned off or unreachable. Tested models and anything already installed still work.",
            })}
          </p>
        ) : results.data.results.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "models_search_no_results_empty",
                defaultMessage: "No models match “{query}”.",
              },
              { query: trimmed }
            )}
          </p>
        ) : (
          // The cap is the reserved height less the 1px border top and
          // bottom, so a full list fills the space exactly and moves nothing.
          <ScrollFade
            className="overflow-hidden rounded-xl border bg-card"
            viewportClassName="max-h-[calc(20rem-2px)]"
          >
            <ul
              className="divide-y"
              aria-label={intl.formatMessage({
                id: "models_search_results_aria",
                defaultMessage: "Search results",
              })}
            >
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
                            <Badge variant="secondary">
                              {intl.formatMessage({
                                id: "models_search_vision_label",
                                defaultMessage: "Vision",
                              })}
                            </Badge>
                          ) : null}
                          {hit.gated ? (
                            <Badge variant="outline">
                              {intl.formatMessage({
                                id: "models_search_gated_label",
                                defaultMessage: "Needs an account",
                              })}
                            </Badge>
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
                          installs={installs}
                          disabled={disabled}
                        />
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </ScrollFade>
        )}
      </div>
    </section>
  )
}
