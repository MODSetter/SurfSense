import { useRef, useState, type KeyboardEvent, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ArrowRight02Icon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { intl } from "@/i18n/intl"

import type { WebResult } from "./api"
import { pastedLinks } from "./pasted-links"
import { notALinkText } from "./refusal-text"
import type { RowActions, RowState } from "./row-actions"
import { searchSiteName, type SearchSite } from "./search-sites"
import { SearchSitePicker } from "./search-site-picker"
import { ShowMoreButton } from "./show-more-button"
import type { WebSources } from "./use-web-sources"
import { webProblem, type WebProblem } from "./web-problem"
import { WebResultRows } from "./web-result-rows"
import { WebSearchStart } from "./web-search-start"

// Per request, as the API takes them.
const MAX_LINKS = 20

/** The next page's rows under those shown, without repeating one. */
function appended(shown: WebResult[], next: WebResult[]): WebResult[] {
  return [
    ...shown,
    ...next.filter((result) => !shown.some((row) => row.url === result.url)),
  ]
}

export function AddFromWebDialog({
  open,
  web,
  onOpenChange,
}: {
  open: boolean
  web: WebSources
  onOpenChange: (open: boolean) => void
}) {
  const [text, setText] = useState("")
  const [site, setSite] = useState<SearchSite>("web")
  // The search the shown rows came from, for its Show more.
  const [searched, setSearched] = useState<{
    query: string
    site: SearchSite
  } | null>(null)
  const [rows, setRows] = useState<WebResult[] | null>(null)
  const [more, setMore] = useState(false)
  const [page, setPage] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [busy, setBusy] = useState<"searching" | "opening" | null>(null)
  const [problem, setProblem] = useState<WebProblem | null>(null)
  const [states, setStates] = useState<ReadonlyMap<string, RowState>>(
    () => new Map()
  )
  const [notLinks, setNotLinks] = useState<string[]>([])
  const run = useRef<AbortController | null>(null)
  const box = useRef<HTMLTextAreaElement>(null)

  const pasted = pastedLinks(text)
  const addable = [
    ...new Set(
      (rows ?? [])
        .filter((result) => !states.has(result.url))
        .map((result) => result.url)
    ),
  ]

  const mark = (urls: string[], state: RowState | null) =>
    setStates((current) => {
      const next = new Map(current)
      for (const url of urls) {
        if (state) next.set(url, state)
        else next.delete(url)
      }
      return next
    })

  const fail = (cause: unknown) => setProblem(webProblem(cause))

  // Text with links opens them; anything else is a search where the pill says.
  const submit = async (event?: SubmitEvent) => {
    event?.preventDefault()
    const asked = text.trim()
    if (!asked || busy) return
    run.current?.abort()
    const thisRun = new AbortController()
    run.current = thisRun
    const opening = pasted.links.length > 0
    setBusy(opening ? "opening" : "searching")
    setProblem(null)
    setNotLinks(opening ? pasted.notLinks : [])
    // The last rows go at once: Add all must never count rows no longer shown.
    setRows(null)
    setMore(false)
    setPage(0)
    setLoadingMore(false)
    setSearched(opening ? null : { query: asked, site })
    // Added stays true across searches.
    setStates(
      (current) =>
        new Map(
          [...current].filter(
            ([, state]) => state === "added" || state === "already"
          )
        )
    )
    try {
      if (opening) {
        setRows(
          await web.open(pasted.links.slice(0, MAX_LINKS), thisRun.signal)
        )
      } else {
        const found = await web.search(asked, site, 0, thisRun.signal)
        setRows(found.results)
        setMore(found.more)
      }
    } catch (cause) {
      if (!thisRun.signal.aborted) fail(cause)
    } finally {
      if (run.current === thisRun) setBusy(null)
    }
  }

  const add = async (urls: string[]) => {
    setProblem(null)
    for (let start = 0; start < urls.length; start += MAX_LINKS) {
      const batch = urls.slice(start, start + MAX_LINKS)
      mark(batch, "adding")
      try {
        const outcome = await web.add(batch)
        const already = outcome.duplicates.map((duplicate) => duplicate.url)
        mark(already, "already")
        mark(
          batch.filter((url) => !already.includes(url)),
          "added"
        )
      } catch (cause) {
        mark(urls.slice(start), null)
        fail(cause)
        return
      }
    }
  }

  // The search's next page belongs to the rows it was asked from.
  const showMore = async () => {
    if (!searched) return
    const shownRun = run.current
    const next = page + 1
    setLoadingMore(true)
    try {
      const found = await web.search(searched.query, searched.site, next)
      if (run.current !== shownRun) return
      setRows((current) => appended(current ?? [], found.results))
      setMore(found.more)
      setPage(next)
    } catch (cause) {
      if (run.current === shownRun) fail(cause)
    } finally {
      // A newer search already cleared it.
      if (run.current === shownRun) setLoadingMore(false)
    }
  }

  const actions: RowActions = {
    states,
    onAdd: (url) => void add([url]),
  }

  const submitOnEnter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    )
      return
    event.preventDefault()
    void submit()
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(next) => {
        if (next) return
        run.current?.abort()
        setText("")
        setRows(null)
        setMore(false)
        setPage(0)
        setLoadingMore(false)
        setSearched(null)
        setSite("web")
        setBusy(null)
        setProblem(null)
        setStates(new Map())
        setNotLinks([])
      }}
    >
      {/* A fixed height: the box stays put while results scroll beneath it. */}
      <DialogContent className="flex h-[min(42rem,calc(100dvh-2rem))] flex-col select-none sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage({
              id: "sources_web_dialog_title",
              defaultMessage: "Add from the web",
            })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "sources_web_dialog_body",
              defaultMessage:
                "Search the web or paste links, then add what you want as sources.",
            })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
          {/* One box like the chat composer's: the text, then where it searches. */}
          <form
            className="shrink-0 rounded-2xl border bg-card p-1.5 shadow-sm transition-colors focus-within:border-ring/40 hover:border-ring/40"
            onSubmit={(event) => void submit(event)}
          >
            <Textarea
              ref={box}
              value={text}
              rows={1}
              className="max-h-40 min-h-11 resize-none border-0 bg-transparent px-2 py-2.5 shadow-none select-text focus-visible:border-0 dark:bg-transparent"
              aria-label={intl.formatMessage({
                id: "sources_web_box_aria",
                defaultMessage: "Search or paste links",
              })}
              placeholder={
                site === "web"
                  ? intl.formatMessage({
                      id: "sources_web_box_placeholder",
                      defaultMessage: "Search the web or paste links",
                    })
                  : intl.formatMessage(
                      {
                        id: "sources_web_box_site_placeholder",
                        defaultMessage: "Search {site} or paste links",
                      },
                      { site: searchSiteName(site) }
                    )
              }
              onChange={(event) => setText(event.target.value)}
              onKeyDown={submitOnEnter}
            />
            <div className="flex items-center justify-between gap-2">
              <SearchSitePicker site={site} onSiteChange={setSite} />
              <Button
                type="submit"
                size="icon-lg"
                className="rounded-xl"
                disabled={!text.trim() || busy !== null}
                aria-label={
                  pasted.links.length > 0
                    ? intl.formatMessage({
                        id: "sources_web_open_links_button",
                        defaultMessage: "Open links",
                      })
                    : intl.formatMessage({
                        id: "sources_web_search_button",
                        defaultMessage: "Search",
                      })
                }
              >
                {busy ? <Spinner /> : <ArrowRight02Icon />}
              </Button>
            </div>
          </form>
          {notLinks.length > 0 ? (
            <ul className="flex shrink-0 flex-col gap-1 text-sm text-muted-foreground">
              {notLinks.map((notLink) => (
                <li key={notLink} className="min-w-0 truncate">
                  <span className="text-foreground">{notLink}</span>{" "}
                  {notALinkText()}
                </li>
              ))}
            </ul>
          ) : null}
          {problem ? (
            <p role="alert" className="shrink-0 text-sm text-destructive">
              {problemText(problem)}
            </p>
          ) : null}
          {busy ? (
            <p className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
              <Spinner className="size-5" />
              {busy === "searching"
                ? intl.formatMessage({
                    id: "sources_web_searching_status",
                    defaultMessage: "Searching. This can take a minute.",
                  })
                : intl.formatMessage({
                    id: "sources_web_opening_status",
                    defaultMessage: "Opening links. This can take a minute.",
                  })}
            </p>
          ) : rows ? (
            <ScrollFade
              className="flex-1 rounded-lg border"
              viewportClassName="flex flex-col gap-2 p-1"
            >
              {rows.length === 0 ? (
                <p className="flex flex-1 items-center justify-center px-3 py-6 text-center text-sm text-muted-foreground">
                  {intl.formatMessage({
                    id: "sources_web_results_empty",
                    defaultMessage: "No results. Try other words.",
                  })}
                </p>
              ) : (
                <div className="flex flex-col">
                  <WebResultRows results={rows} actions={actions} />
                  {searched && more ? (
                    <ShowMoreButton
                      loading={loadingMore}
                      onClick={() => void showMore()}
                    />
                  ) : null}
                </div>
              )}
            </ScrollFade>
          ) : (
            <WebSearchStart
              site={site}
              onSiteChange={(next) => {
                setSite(next)
                box.current?.focus()
              }}
            />
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {intl.formatMessage({
              id: "sources_web_close_button",
              defaultMessage: "Close",
            })}
          </Button>
          {addable.length > 0 ? (
            <Button type="button" onClick={() => void add(addable)}>
              {intl.formatMessage(
                {
                  id: "sources_web_add_all_button",
                  defaultMessage: "Add all ({count, number})",
                },
                { count: addable.length }
              )}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function problemText(problem: WebProblem): string {
  if (problem.kind === "search_unreachable") {
    return intl.formatMessage(
      {
        id: "sources_web_search_unreachable_error",
        defaultMessage:
          "SurfSense couldn’t reach the search server at {host}. Check your connection, or choose another server in Settings › Network.",
      },
      { host: problem.host }
    )
  }
  if (problem.kind === "search_failed") {
    return intl.formatMessage(
      {
        id: "sources_web_search_failed_error",
        defaultMessage:
          "The search server at {host} didn’t search this time. Try again, or choose another server in Settings › Network.",
      },
      { host: problem.host }
    )
  }
  if (problem.kind === "network_off") {
    return intl.formatMessage(
      {
        id: "sources_web_network_off_error",
        defaultMessage:
          "This needs {hosts} to be allowed in Settings › Network.",
      },
      { hosts: intl.formatList(problem.hosts, { type: "conjunction" }) }
    )
  }
  return intl.formatMessage({
    id: "sources_web_failed_error",
    defaultMessage: "Something went wrong. Try again.",
  })
}
