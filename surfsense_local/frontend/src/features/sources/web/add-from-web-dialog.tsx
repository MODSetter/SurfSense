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
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useLicense } from "@/features/license/use-license"
import { intl } from "@/i18n/intl"

import type { WebGroup } from "./api"
import { pastedLinks } from "./pasted-links"
import { refusalText } from "./refusal-text"
import type { WebSources } from "./use-web-sources"
import { WebLicenseOffer } from "./web-license-offer"
import { webProblem, type WebProblem } from "./web-problem"
import type { RowActions, RowState } from "./row-actions"
import { WebListPanel } from "./web-list-panel"
import { WebResultRows } from "./web-result-rows"

// Per request, as the API takes them.
const MAX_LINKS = 20

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

  // Text with links opens them; anything else is a Google search.
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
          : [await web.search(asked, thisRun.signal)]
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
      mark([url], "opened")
    } catch (cause) {
      // Aborted by the newer search or paste, which owns the rows now.
      if (run.current !== shownRun) return
      mark([url], null)
      fail(cause)
    }
  }

  const showMore = async (link: string) => {
    const page = (pages.get(link) ?? 0) + 1
    setLoadingMore((current) => new Set(current).add(link))
    try {
      const next = await web.list(link, page)
      const grown = (group: WebGroup): WebGroup =>
        group.link === link
          ? {
              ...group,
              // A list that moved between pages repeats an item already shown.
              results: [
                ...group.results,
                ...next.results.filter(
                  (result) =>
                    !group.results.some((shown) => shown.url === result.url)
                ),
              ],
              more: next.more,
              failed: next.failed,
            }
          : group
      setGroups((current) => current?.map(grown) ?? null)
      setLists((current) => {
        const shown = current.get(link)
        return shown ? new Map(current).set(link, grown(shown)) : current
      })
      setPages((current) => new Map(current).set(link, page))
    } catch (cause) {
      fail(cause)
    } finally {
      setLoadingMore((current) => {
        const next = new Set(current)
        next.delete(link)
        return next
      })
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
        setBusy(null)
        setProblem(null)
        setStates(new Map())
        setNotLinks([])
        setPages(new Map())
        setLoadingMore(new Set())
      }}
    >
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
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
          <div className="flex min-w-0 flex-col gap-4">
            <form
              className="flex items-start gap-2"
              onSubmit={(event) => void submit(event)}
            >
              <Textarea
                value={text}
                rows={1}
                className="max-h-40 min-h-9 resize-none"
                aria-label={intl.formatMessage({
                  id: "sources_web_box_aria",
                  defaultMessage: "Search Google or paste links",
                })}
                placeholder={intl.formatMessage({
                  id: "sources_web_box_placeholder",
                  defaultMessage: "Search Google or paste links",
                })}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={submitOnEnter}
              />
              <Button type="submit" disabled={!text.trim() || busy !== null}>
                {pasted.links.length > 0
                  ? intl.formatMessage({
                      id: "sources_web_open_links_button",
                      defaultMessage: "Open links",
                    })
                  : intl.formatMessage({
                      id: "sources_web_search_button",
                      defaultMessage: "Search",
                    })}
              </Button>
            </form>
            {busy ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                {busy === "searching"
                  ? intl.formatMessage({
                      id: "sources_web_searching_status",
                      defaultMessage:
                        "Searching Google. This can take a minute.",
                    })
                  : intl.formatMessage({
                      id: "sources_web_opening_status",
                      defaultMessage: "Opening links. This can take a minute.",
                    })}
              </p>
            ) : null}
            {notLinks.length > 0 ? (
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                {notLinks.map((notLink) => (
                  <li key={notLink} className="min-w-0 truncate">
                    <span className="text-foreground">{notLink}</span>{" "}
                    {refusalText("not_a_link")}
                  </li>
                ))}
              </ul>
            ) : null}
            {problem && problem.kind !== "license" ? (
              <p role="alert" className="text-sm text-destructive">
                {problemText(problem)}
              </p>
            ) : null}
            {groups && !busy ? (
              <div className="flex max-h-[60dvh] flex-col gap-2 overflow-y-auto rounded-lg border p-1">
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
                      className="px-3 py-6 text-center text-sm text-muted-foreground"
                    >
                      {intl.formatMessage({
                        id: "sources_web_results_empty",
                        defaultMessage: "No results. Try other words.",
                      })}
                    </p>
                  ) : (
                    <WebResultRows
                      key={`rows-${index}`}
                      results={group.results}
                      actions={actions}
                    />
                  )
                )}
              </div>
            ) : null}
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
      defaultMessage: "Google didn’t answer this time. Try again.",
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
