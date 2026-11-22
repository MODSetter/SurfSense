import { createNoiseFloor } from "./noise-floor"

const FRAME_MS = 20
const frames = (ms: number) => Math.ceil(ms / FRAME_MS)

// Handy's pre-roll and hangover: the onset and the last word, which sit under
// the threshold, stay in the phrase.
const PRE_ROLL_FRAMES = frames(450)
const TAIL_FRAMES = frames(450)
// A word or two alone is transcribed worse than with its neighbours.
const MIN_VOICE_FRAMES = frames(1000)
const PAUSE_FRAMES = frames(700)
// Well under the API's 30 s per phrase, and one encoder graph's memory.
const MAX_PHRASE_FRAMES = frames(20_000)
const CUT_FRAMES = frames(200)
// A forced cut looks only in the phrase's second half, so neither piece is short.
const CUT_SEARCH_FROM = MAX_PHRASE_FRAMES / 2

const SPEECH_OVER_FLOOR = 3
// About -46 dBFS (RMS): what a still room and Chromium's noise suppression
// leave stays under it, so a quiet room's floor alone never counts as speech.
export const SPEECH_MIN_LEVEL = 0.005

type Frame = { samples: Float32Array; level: number; voiced: boolean }

function joined(frames: readonly Frame[]): Float32Array {
  const length = frames.reduce((sum, frame) => sum + frame.samples.length, 0)
  const out = new Float32Array(length)
  let offset = 0
  for (const frame of frames) {
    out.set(frame.samples, offset)
    offset += frame.samples.length
  }
  return out
}

/** The index after the quietest run of CUT_FRAMES in the search range. */
function quietestCut(phrase: readonly Frame[]): number {
  let best = CUT_SEARCH_FROM
  let bestSum = Infinity
  for (
    let start = CUT_SEARCH_FROM;
    start + CUT_FRAMES <= phrase.length;
    start++
  ) {
    let sum = 0
    for (let i = start; i < start + CUT_FRAMES; i++) sum += phrase[i].level
    if (sum < bestSum) {
      bestSum = sum
      best = start
    }
  }
  // Mid-silence: no word straddles the cut, so the pieces need no overlap.
  return best + Math.floor(CUT_FRAMES / 2)
}

/**
 * Splits the microphone's 20 ms frames into phrases at the speaker's pauses,
 * so each can be transcribed while they go on talking.
 */
export function createPhraseCutter() {
  const floor = createNoiseFloor()
  let before: Frame[] = []
  let phrase: Frame[] | null = null

  const voicedIn = (frames: readonly Frame[]) =>
    frames.filter((frame) => frame.voiced).length

  /** The phrase up to its tail; what follows waits as the next one's pre-roll. */
  const close = (frames: Frame[]): Float32Array => {
    const lastVoiced = frames.findLastIndex((frame) => frame.voiced)
    const end = Math.min(frames.length, lastVoiced + 1 + TAIL_FRAMES)
    before = frames.slice(end).slice(-PRE_ROLL_FRAMES)
    phrase = null
    return joined(frames.slice(0, end))
  }

  return {
    /** Takes one frame; answers a phrase when this frame ended one. */
    push(samples: Float32Array, level: number): Float32Array | null {
      const threshold = Math.max(
        floor.add(level) * SPEECH_OVER_FLOOR,
        SPEECH_MIN_LEVEL
      )
      const frame = { samples, level, voiced: level > threshold }

      if (phrase === null) {
        if (!frame.voiced) {
          before.push(frame)
          if (before.length > PRE_ROLL_FRAMES) before.shift()
          return null
        }
        phrase = [...before, frame]
        before = []
        return null
      }

      phrase.push(frame)
      const pause = phrase.length - 1 - phrase.findLastIndex((f) => f.voiced)
      if (pause >= PAUSE_FRAMES && voicedIn(phrase) >= MIN_VOICE_FRAMES) {
        return close(phrase)
      }
      if (phrase.length >= MAX_PHRASE_FRAMES) {
        const cut = quietestCut(phrase)
        const rest = phrase.slice(cut)
        // Only quiet left after the cut: the phrase ends at its last word, so
        // the quiet is never sent, alone or ahead of the next phrase.
        if (voicedIn(rest) === 0) return close(phrase)
        const done = joined(phrase.slice(0, cut))
        phrase = rest
        return done
      }
      return null
    },

    /** The phrase in progress when the speaker stops; null when there is none. */
    flush(): Float32Array | null {
      if (phrase === null || voicedIn(phrase) === 0) return null
      return close(phrase)
    },
  }
}
