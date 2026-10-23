import { useMemo } from "react"
import { toast } from "sonner"

import { useStableCallback } from "@/hooks/use-stable-callback"
import { intl } from "@/i18n/intl"

import type { WorkspaceDocument } from "../api"
import {
  addWebLinks,
  listWebLink,
  openWebLinks,
  searchWeb,
  type WebGroup,
  type WebLinksOutcome,
} from "./api"

/** What the Add from the web dialog needs from its owner; each throws what it shows instead. */
export type WebSources = {
  search: (
    query: string,
    source: string,
    page: number,
    signal?: AbortSignal
  ) => Promise<WebGroup>
  open: (urls: string[], signal?: AbortSignal) => Promise<WebGroup[]>
  list: (url: string, page: number) => Promise<WebGroup>
  add: (urls: string[]) => Promise<WebLinksOutcome>
  onOpenLicense: () => void
}

export function useWebSources(
  workspaceId: number,
  addCreated: (created: WorkspaceDocument[]) => void,
  onOpenLicense: () => void
): WebSources {
  const search = useStableCallback(
    (query: string, source: string, page: number, signal?: AbortSignal) =>
      searchWeb(workspaceId, query, source, page, signal)
  )
  const open = useStableCallback((urls: string[], signal?: AbortSignal) =>
    openWebLinks(workspaceId, urls, signal)
  )
  const list = useStableCallback((url: string, page: number) =>
    listWebLink(workspaceId, url, page)
  )
  const add = useStableCallback(async (urls: string[]) => {
    const outcome = await addWebLinks(workspaceId, urls)
    // Created in the order asked; the list is newest first, as uploads keep it.
    addCreated([...outcome.created].reverse())
    announce(outcome)
    return outcome
  })
  const openLicense = useStableCallback(() => onOpenLicense())
  return useMemo(
    () => ({ search, open, list, add, onOpenLicense: openLicense }),
    [search, open, list, add, openLicense]
  )
}

function announce(outcome: WebLinksOutcome) {
  const already =
    outcome.duplicates.length === 0
      ? undefined
      : intl.formatMessage(
          {
            id: "sources_web_duplicates_body",
            defaultMessage:
              "{count, plural, one {# link was} other {# links were}} already in Sources.",
          },
          { count: outcome.duplicates.length }
        )
  if (outcome.created.length === 0) {
    if (already) toast.info(already)
    return
  }
  toast.success(
    intl.formatMessage(
      {
        id: "sources_web_added_toast",
        defaultMessage:
          "{count, plural, one {Adding # source} other {Adding # sources}} from the web",
      },
      { count: outcome.created.length }
    ),
    {
      description:
        already ??
        intl.formatMessage({
          id: "sources_web_added_body",
          defaultMessage:
            "Each one is ready to use once SurfSense has read it.",
        }),
    }
  )
}
