import { useEffect, useState } from "react"

import { messageFrom } from "./use-studio"

import { readPodcastBrief, type OpenedBrief, type PodcastBrief } from "./api"

/** The brief the server proposes, held for the user to edit before generating.
 *  Pass null for other formats: nothing loads. */
export function usePodcastBrief(workspaceId: number | null) {
  const [brief, setBrief] = useState<PodcastBrief | null>(null)
  // What the brief was opened with, beside the brief the user edits.
  const [opened, setOpened] = useState<Omit<OpenedBrief, "brief"> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (workspaceId == null) return
    const controller = new AbortController()
    readPodcastBrief(workspaceId, controller.signal)
      .then(({ brief, ...rest }) => {
        setBrief(brief)
        setOpened(rest)
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
    return () => controller.abort()
  }, [workspaceId])

  return { brief, opened, error, setBrief }
}
