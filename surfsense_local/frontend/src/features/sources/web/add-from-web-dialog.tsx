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
import { useLicense } from "@/features/license/use-license"
import { intl } from "@/i18n/intl"

import type { WebGroup } from "./api"
import { pastedLinks } from "./pasted-links"
import { refusalText } from "./refusal-text"
import { searchSiteName, type SearchSite } from "./search-sites"
import { SearchSitePicker } from "./search-site-picker"
import { ShowMoreButton } from "./show-more-button"
import type { WebSources } from "./use-web-sources"
import { WebLicenseOffer } from "./web-license-offer"
import { webProblem, type WebProblem } from "./web-problem"
import type { RowActions, RowState } from "./row-actions"
import { WebListPanel } from "./web-list-panel"
import { WebResultRows } from "./web-result-rows"
import { WebSearchStart } from "./web-search-start"

// Per request, as the API takes them.
const MAX_LINKS = 20
// The last search's key in `pages` and `loadingMore`, beside the lists' links.
const SEARCH = "search"

/** A list page added under the rows already shown, without repeating one. */
function appended(group: WebGroup, next: WebGroup): WebGroup {
  return {
    ...group,
    // A list that moved between pages repeats an item already shown.
    results: [
      ...group.results,
      ...next.results.filter(
        (result) => !group.results.some((shown) => shown.url === result.url)
      ),
    ],
    more: next.more,
    failed: next.failed,
  }
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
  const license = useLicense()
  const [text, setText] = useState("")
  const [site, setSite] = useState<SearchSite>("web")
  // The search the shown rows came from, for its Show more.
  const [searched, setSearched] = useState<{
    query: string
    site: SearchSite
  } | null>(null)
  const [groups, setGroups] = useState<WebGroup[] | null>(null)
  // Lists opened from a row, by the row's link; shown beneath that row.
  const [lists, setLists] = useState<ReadonlyMap<string, WebGroup>>(
    () => new Map()
  )
  const [busy, setBusy] = useState<"searching" | "opening" | null>(null)
  const [problem, setProblem] = useState<WebProblem | null>(null)
  const [states, setStates] = useState<ReadonlyMap<string, RowState>>(
    () => new Map()
  )
  const [notLinks, setNotLinks] = useState<string[]>([])
  const [pages, setPages] = useState<ReadonlyMap<string, number>>(
    () => new Map()
  )
  const [loadingMore, setLoadingMore] = useState<ReadonlySet<string>>(
    () => new Set()
  )
  const run = useRef<AbortController | null>(null)
  const box = useRef<HTMLTextAreaElement>(null)

  const pasted = pastedLinks(text)
  const addable = [...(groups ?? []), ...lists.values()]
    .flatMap((group) => group.results)
    .filter((result) => result.fit === "one" && !states.has(result.url))
    .map((result) => result.url)
  const uniqueAddable = [...new Set(addable)]
  // The app's own record first; a refusal from the plugin host on the way wins.
  const offerReason =
    problem?.kind === "license"
      ? problem.reason
      : license.data?.state === "none"
        ? "missing_license"
        : license.data?.state === "license_expired"
          ? "expired"
          : null

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

  // Text with links opens them, by their own site; anything else is a search
  // on the site chosen beside the box.
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
    setGroups(null)
    setLists(new Map())
    setPages(new Map())
    setLoadingMore(new Set())
    setSearched(opening ? null : { query: asked, site })
    // Added stays true across searches; an opened list belonged to the last rows.
    setStates(
      (current) =>
        new Map(
          [...current].filter(
            ([, state]) => state === "added" || state === "already"
          )
        )
    )
    try {
      setGroups(
        opening
          ? await web.open(pasted.links.slice(0, MAX_LINKS), thisRun.signal)
          : [await web.search(asked, site, 0, thisRun.signal)]
      )
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
        const refused = outcome.rejected.map((rejected) => rejected.url)
        mark(already, "already")
        mark(refused, null)
        mark(
          batch.filter(
            (url) => !already.includes(url) && !refused.includes(url)
          ),
          "added"
        )
      } catch (cause) {
        mark(urls.slice(start), null)
        fail(cause)
        return
      }
    }
  }

  // Belongs to the rows it was opened from: a newer search or paste drops it.
  const openList = async (url: string) => {
    const shownRun = run.current
    setProblem(null)
    mark([url], "opening")
    try {
      const [opened] = await web.open([url], shownRun?.signal)
      if (run.current !== shownRun) return
      if (opened) setLists((current) => new Map(current).set(url, opened))
      // A list that failed keeps its panel's error and its Open, to try again.
      mark([url], opened && !opened.failed ? "opened" : null)
    } catch (cause) {
      // Aborted by the newer search or paste, which owns the rows now.
      if (run.current !== shownRun) return
      mark([url], null)
      fail(cause)
    }
  }

  // Like openList, a page belongs to the rows it was asked from.
  const showMore = async (link: string) => {
    const shownRun = run.current
    const page = (pages.get(link) ?? 0) + 1
    setLoadingMore((current) => new Set(current).add(link))
    try {
      const next = await web.list(link, page)
      if (run.current !== shownRun) return
      const grown = (group: WebGroup): WebGroup =>
        group.link === link ? appended(group, next) : group
      setGroups((current) => current?.map(grown) ?? null)
      setLists((current) => {
        const shown = current.get(link)
        return shown ? new Map(current).set(link, grown(shown)) : current
      })
      setPages((current) => new Map(current).set(link, page))
    } catch (cause) {
      if (run.current === shownRun) fail(cause)
    } finally {
      // A newer search already cleared it, and may be loading this link again.
      if (run.current === shownRun) {
        setLoadingMore((current) => {
          const next = new Set(current)
          next.delete(link)
          return next
        })
      }
    }
  }

  // The search's next page, under its rows: Show more as on a list.
  const showMoreSearch = async () => {
    if (!searched) return
    const shownRun = run.current
    const page = (pages.get(SEARCH) ?? 0) + 1
    setLoadingMore((current) => new Set(current).add(SEARCH))
    try {
      const next = await web.search(searched.query, searched.site, page)
      if (run.current !== shownRun) return
      setGroups(
        (current) =>
          current?.map((group, index) =>
            index === 0 ? appended(group, next) : group
          ) ?? null
      )
      setPages((current) => new Map(current).set(SEARCH, page))
    } catch (cause) {
      if (run.current === shownRun) fail(cause)
    } finally {
      if (run.current === shownRun) {
        setLoadingMore((current) => {
          const next = new Set(current)
          next.delete(SEARCH)
          return next
        })
      }
    }
  }

  const actions: RowActions = {
    states,
    lists,
    loadingMore,
    onAdd: (url) => void add([url]),
    onOpen: (url) => void openList(url),
    onMore: (link) => void showMore(link),
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
        setGroups(null)
        setLists(new Map())
        setSearched(null)
        setSite("web")
        setBusy(null)
        setProblem(null)
        setStates(new Map())
        setNotLinks([])
        setPages(new Map())
        setLoadingMore(new Set())
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
        {offerReason ? (
          <WebLicenseOffer
            reason={offerReason}
            onOpenLicense={web.onOpenLicense}
          />
        ) : (
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
                        defaultMessage: "Search Google or paste links",
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
                    {refusalText("not_a_link")}
                  </li>
                ))}
              </ul>
            ) : null}
            {problem && problem.kind !== "license" ? (
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
            ) : groups ? (
              <ScrollFade
                className="flex-1 rounded-lg border"
                viewportClassName="flex flex-col gap-2 p-1"
              >
                {groups.map((group, index) =>
                  group.link ? (
                    <WebListPanel
                      key={group.link}
                      title={group.link}
                      group={group}
                      actions={actions}
                    />
                  ) : group.results.length === 0 ? (
                    <p
                      key={`rows-${index}`}
                      className="flex flex-1 items-center justify-center px-3 py-6 text-center text-sm text-muted-foreground"
                    >
                      {intl.formatMessage({
                        id: "sources_web_results_empty",
                        defaultMessage: "No results. Try other words.",
                      })}
                    </p>
                  ) : (
                    <div key={`rows-${index}`} className="flex flex-col">
                      <WebResultRows
                        results={group.results}
                        actions={actions}
                      />
                      {searched && index === 0 && group.more ? (
                        <ShowMoreButton
                          loading={loadingMore.has(SEARCH)}
                          onClick={() => void showMoreSearch()}
                        />
                      ) : null}
                    </div>
                  )
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
        )}
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
          {!offerReason && uniqueAddable.length > 0 ? (
            <Button type="button" onClick={() => void add(uniqueAddable)}>
              {intl.formatMessage(
                {
                  id: "sources_web_add_all_button",
                  defaultMessage: "Add all ({count, number})",
                },
                { count: uniqueAddable.length }
              )}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function problemText(problem: WebProblem): string {
  if (problem.kind === "unreachable") {
    return intl.formatMessage({
      id: "sources_web_unreachable_error",
      defaultMessage:
        "SurfSense couldn’t reach the web just now. Try again in a moment.",
    })
  }
  if (problem.kind === "search_failed") {
    return intl.formatMessage({
      id: "sources_web_search_failed_error",
      defaultMessage: "The search didn’t answer this time. Try again.",
    })
  }
  if (problem.kind === "network_off") {
    return intl.formatMessage({
      id: "sources_web_network_off_error",
      defaultMessage:
        "Adding from the web needs plugins.surfsense.com to be allowed in Settings › Network.",
    })
  }
  return intl.formatMessage({
    id: "sources_web_failed_error",
    defaultMessage: "Something went wrong. Try again.",
  })
}
