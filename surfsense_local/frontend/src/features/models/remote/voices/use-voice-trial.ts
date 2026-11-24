import { useCallback, useEffect, useRef, useState } from "react"

export type VoiceTrial = {
  voice: string
  state: "loading" | "playing"
}

/**
 * Plays one voice's line at a time, with no player on the page. A clip is kept
 * while this is mounted, because asking the server again may be billed again.
 */
export function useVoiceTrial(
  /** Names a clip, so another model's voice of the same id is asked for. */
  clipKey: (voice: string) => string,
  speak: (voice: string, signal: AbortSignal) => Promise<Blob>,
  messageFrom: (cause: unknown) => string
) {
  const [trial, setTrial] = useState<VoiceTrial | null>(null)
  const [failure, setFailure] = useState<{
    voice: string
    message: string
  } | null>(null)
  const clips = useRef(new Map<string, string>())
  const audio = useRef<HTMLAudioElement | null>(null)
  const asking = useRef<AbortController | null>(null)

  const silence = useCallback(() => {
    asking.current?.abort()
    asking.current = null
    audio.current?.pause()
    audio.current = null
  }, [])

  useEffect(() => {
    const kept = clips.current
    return () => {
      silence()
      kept.forEach((clip) => URL.revokeObjectURL(clip))
      kept.clear()
    }
  }, [silence])

  const stop = () => {
    silence()
    setTrial(null)
  }

  const play = async (voice: string) => {
    silence()
    setFailure(null)
    // Made within the click, which is what lets a stricter browser play it.
    const element = new Audio()
    audio.current = element
    const current = () => audio.current === element
    const fail = (cause: unknown) => {
      if (!current()) return
      audio.current = null
      setFailure({ voice, message: messageFrom(cause) })
      setTrial(null)
    }
    element.onended = () => {
      if (current()) setTrial(null)
    }
    // After play() resolved, as with no audio device, which it cannot reject for.
    element.onerror = () =>
      fail(element.error?.message ? new Error(element.error.message) : null)
    setTrial({ voice, state: "loading" })
    const key = clipKey(voice)
    try {
      let clip = clips.current.get(key)
      if (!clip) {
        const controller = new AbortController()
        asking.current = controller
        clip = URL.createObjectURL(await speak(voice, controller.signal))
        clips.current.set(key, clip)
      }
      if (!current()) return
      element.src = clip
      await element.play()
      if (current()) setTrial({ voice, state: "playing" })
    } catch (cause) {
      fail(cause)
    }
  }

  return { trial, failure, play, stop }
}
