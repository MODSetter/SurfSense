import { useEffect, useState } from "react"

import { messageFrom } from "./use-studio"

import { readPodcastBrief, type PodcastBrief, type Voice } from "./api"

/** The brief the server proposes, held for the user to edit before generating.
 *  Pass null for other formats: nothing loads. */
export function usePodcastBrief(workspaceId: number | null) {
  const [brief, setBrief] = useState<PodcastBrief | null>(null)
  const [voices, setVoices] = useState<Voice[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (workspaceId == null) return
    const controller = new AbortController()
    readPodcastBrief(workspaceId, controller.signal)
      .then((opened) => {
        setBrief(opened.brief)
        setVoices(opened.voices)
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
    return () => controller.abort()
  }, [workspaceId])

  return { brief, voices, error, setBrief }
}
