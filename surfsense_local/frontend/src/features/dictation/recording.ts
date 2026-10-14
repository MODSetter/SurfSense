import type { DictationAdapter, Unsubscribe } from "@assistant-ui/react"

import { ApiError } from "@/lib/api"

import { encodeWav } from "./capture/encode-wav"
import type {
  Microphone,
  MicrophoneFrame,
  OpenMicrophone,
} from "./capture/open-microphone"
import { createPhraseCutter } from "./capture/phrase-cutter"
import { resampleForSpeech, SPEECH_SAMPLE_RATE } from "./capture/resample"
import { clampToRoom } from "./clamp-to-room"
import {
  microphoneProblem,
  openingProblem,
  type DictationProblem,
} from "./dictation-problem"
import {
  isDictationEnded,
  openDictationSession,
  type DictationSession,
} from "./dictation-session"
import type { PhraseText } from "./api"
import { joinPhrases, type TranscribedPhrase } from "./join-phrases"

const WARN_AT_MS = 270_000
const STOP_AT_MS = 300_000
// Handy's: a warm load takes under 2 s, so only a slower one is worth a word.
const LOADING_NOTICE_MS = 2_000

/** What a recording shows while it lasts. */
export type RecordingView =
  | { phase: "arming" }
  | { phase: "listening"; since: number; warning: boolean; loading: boolean }
  | { phase: "finishing"; loading: boolean }

export type RecordingOutcome = {
  problem: DictationProblem | null
  /** Audio not yet transcribed when a phrase failed, for Retry. */
  kept: Blob[]
}

type RecordingOptions = {
  /** Characters left under the message limit for the dictated text. */
  room: number
  openMicrophone: OpenMicrophone
  /** Audio a failed phrase left: transcribed again, with no microphone. */
  kept?: Blob[]
  onView: (view: RecordingView) => void
  onLevel: (level: number) => void
  /** Once, however it ends. */
  onEnd: (outcome: RecordingOutcome) => void
}

/**
 * One recording, from the mic press to its final text: assistant-ui's
 * dictation session. Phrases go up one at a time as the speaker pauses; each
 * answer re-emits the whole text so far, and stop emits it once as final.
 */
export class Recording implements DictationAdapter.Session {
  status: DictationAdapter.Status = { type: "starting" }

  private readonly options: RecordingOptions

  private readonly speech = new Set<(result: DictationAdapter.Result) => void>()
  private readonly starts = new Set<() => void>()
  private readonly ends = new Set<(result: DictationAdapter.Result) => void>()
  private readonly cutter = createPhraseCutter()
  private session: Promise<DictationSession | null> = Promise.resolve(null)
  private opened: DictationSession | null = null
  private mic: Microphone | null = null
  private chain: Promise<void> = Promise.resolve()
  private phrases: TranscribedPhrase[] = []
  private text = ""
  private pending = 0
  private rate = SPEECH_SAMPLE_RATE
  private since: number | null = null
  private warning = false
  private modelLoading = false
  private loadingNoticed = false
  private loadingTimer: ReturnType<typeof setTimeout> | undefined
  private timers: ReturnType<typeof setTimeout>[] = []
  // False once no more phrases can be sent; `kept` then holds them, if any.
  private sending = true
  private kept: Blob[] | null = null
  private problem: DictationProblem | null = null
  private wrapping = false
  private over = false
  private settle = () => {}
  private readonly done = new Promise<void>((resolve) => {
    this.settle = resolve
  })

  constructor(options: RecordingOptions) {
    this.options = options
  }

  onSpeech(callback: (result: DictationAdapter.Result) => void): Unsubscribe {
    this.speech.add(callback)
    return () => void this.speech.delete(callback)
  }

  onSpeechStart(callback: () => void): Unsubscribe {
    this.starts.add(callback)
    return () => void this.starts.delete(callback)
  }

  onSpeechEnd(
    callback: (result: DictationAdapter.Result) => void
  ): Unsubscribe {
    this.ends.add(callback)
    return () => void this.ends.delete(callback)
  }

  /** Opens the microphone and the API's session side by side. */
  begin(): void {
    if (this.options.room <= 0) {
      this.sending = false
      void this.wrapUp({ kind: "at_limit" })
      return
    }
    this.session = openDictationSession({
      onEnded: () => this.stopSending({ kind: "dictation_ended" }),
    }).then(
      (session) => {
        if (this.over) {
          session.end()
          return null
        }
        this.opened = session
        if (session.warm === "loading") this.noteLoading()
        return session
      },
      (error: unknown) => {
        this.refusedToOpen(openingProblem(error))
        return null
      }
    )
    const retrying = this.options.kept
    if (retrying) {
      for (const wav of retrying) this.enqueue(async () => wav)
      void this.wrapUp(null)
      return
    }
    this.report()
    this.options
      .openMicrophone({
        onFrame: (frame) => this.hear(frame),
        onEnded: () => void this.wrapUp({ kind: "microphone_disconnected" }),
      })
      .then(
        (mic) => {
          if (this.wrapping) mic.close()
          else this.mic = mic
        },
        (error: unknown) => void this.wrapUp(microphoneProblem(error))
      )
  }

  /** Flushes the tail, waits for every phrase, emits the final, then ends. */
  stop(): Promise<void> {
    return this.wrapUp(null)
  }

  /** Drops what is not transcribed yet; nothing lands after this. */
  cancel(): void {
    if (this.over) return
    this.over = true
    this.release()
    this.status = { type: "ended", reason: "cancelled" }
    for (const callback of [...this.ends]) callback({ transcript: "" })
    this.options.onEnd({ problem: null, kept: [] })
    this.settle()
  }

  private hear(frame: MicrophoneFrame) {
    if (this.wrapping || this.over) return
    this.rate = frame.sampleRate
    if (this.since === null) {
      // The first real frame: the device is delivering, so the timer starts.
      this.since = Date.now()
      this.status = { type: "running" }
      for (const callback of [...this.starts]) callback()
      this.timers.push(
        setTimeout(() => {
          this.warning = true
          this.report()
        }, WARN_AT_MS),
        setTimeout(() => void this.wrapUp({ kind: "time_limit" }), STOP_AT_MS)
      )
      this.report()
    }
    this.options.onLevel(frame.level)
    const phrase = this.cutter.push(frame.samples, frame.level)
    if (phrase) this.enqueuePhrase(phrase)
  }

  private enqueuePhrase(samples: Float32Array) {
    const rate = this.rate
    this.enqueue(async () =>
      encodeWav(await resampleForSpeech(samples, rate), SPEECH_SAMPLE_RATE)
    )
  }

  private enqueue(wavOf: () => Promise<Blob>) {
    this.pending += 1
    this.report()
    this.chain = this.chain.then(() => this.transcribe(wavOf))
  }

  private async transcribe(wavOf: () => Promise<Blob>) {
    try {
      if (this.over) return
      const wav = await wavOf()
      if (!this.sending) {
        this.kept?.push(wav)
        return
      }
      const session = await this.session
      if (session === null || this.over) {
        this.kept?.push(wav)
        return
      }
      try {
        const answer = await session.transcribe(wav)
        if (!this.over) this.accept(answer)
      } catch (error) {
        if (!this.over) this.refused(error, wav)
      }
    } catch {
      // Audio that could not be encoded is dropped, never the recording.
    } finally {
      this.pending -= 1
      this.report()
    }
  }

  private accept(answer: PhraseText) {
    this.modelLoading = false
    if (!answer.no_speech && answer.text.trim()) {
      this.phrases.push({ text: answer.text, language: answer.language })
    }
    const joined = joinPhrases(this.phrases)
    const text = clampToRoom(joined, this.options.room)
    if (text !== this.text) {
      this.text = text
      for (const callback of [...this.speech]) {
        callback({ transcript: text, isFinal: false })
      }
    }
    if (text.length < joined.length) this.stopSending({ kind: "at_limit" })
  }

  private refused(error: unknown, wav: Blob) {
    this.modelLoading = false
    if (isDictationEnded(error)) {
      this.stopSending({ kind: "dictation_ended" })
    } else if (
      error instanceof ApiError &&
      error.code === "needs_speech_model"
    ) {
      this.stopSending({ kind: "model_removed" })
    } else {
      // This phrase and every one after it wait for Retry.
      this.kept = [wav]
      this.stopSending({ kind: "phrase_failed" })
    }
  }

  private refusedToOpen(problem: DictationProblem) {
    if (this.options.kept) {
      // A retry keeps its audio whatever stopped it, so Retry stays offered.
      this.kept = []
      this.stopSending({ kind: "phrase_failed" })
    } else {
      this.stopSending(problem)
    }
  }

  private stopSending(problem: DictationProblem) {
    this.sending = false
    void this.wrapUp(problem)
  }

  private wrapUp(problem: DictationProblem | null): Promise<void> {
    if (this.over) return this.done
    if (problem && !this.problem) this.problem = problem
    if (this.wrapping) return this.done
    this.wrapping = true
    this.closeMic()
    this.timers.forEach(clearTimeout)
    if (this.sending || this.kept) {
      const tail = this.cutter.flush()
      if (tail) this.enqueuePhrase(tail)
    }
    this.report()
    // Queued behind every phrase, never awaited from inside one.
    this.chain = this.chain.then(() => this.finish())
    return this.done
  }

  private finish() {
    if (this.over) return
    this.over = true
    this.release()
    // The runtime drops anything emitted once the session has ended.
    for (const callback of [...this.speech]) {
      callback({ transcript: this.text, isFinal: true })
    }
    const notice =
      this.problem === null ||
      this.problem.kind === "at_limit" ||
      this.problem.kind === "time_limit"
    this.status = { type: "ended", reason: notice ? "stopped" : "error" }
    for (const callback of [...this.ends]) {
      callback({ transcript: this.text, isFinal: true })
    }
    this.options.onEnd({ problem: this.problem, kept: this.kept ?? [] })
    this.settle()
  }

  private noteLoading() {
    this.modelLoading = true
    this.loadingTimer = setTimeout(() => {
      this.loadingNoticed = true
      this.report()
    }, LOADING_NOTICE_MS)
  }

  private closeMic() {
    this.mic?.close()
    this.mic = null
  }

  private release() {
    this.closeMic()
    this.timers.forEach(clearTimeout)
    clearTimeout(this.loadingTimer)
    this.opened?.end()
  }

  private report() {
    if (this.over) return
    const loading = this.modelLoading && this.loadingNoticed && this.pending > 0
    if (this.wrapping || this.options.kept) {
      this.options.onView({ phase: "finishing", loading })
    } else if (this.since === null) {
      this.options.onView({ phase: "arming" })
    } else {
      this.options.onView({
        phase: "listening",
        since: this.since,
        warning: this.warning,
        loading,
      })
    }
  }
}
