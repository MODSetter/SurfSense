import { describe, expect, it } from "vitest"

import { createPhraseCutter } from "./phrase-cutter"

// Each frame is 20 ms; its samples all hold the frame's number, so a phrase
// says which frames it kept by its first and last sample.
const SAMPLES_PER_FRAME = 4
const QUIET = 0.001
const VOICE = 0.1

function feed() {
  const cutter = createPhraseCutter()
  let next = 0
  const phrases: { at: number; first: number; last: number; frames: number }[] =
    []
  const push = (count: number, level: number | ((index: number) => number)) => {
    for (let i = 0; i < count; i += 1) {
      const index = next
      next += 1
      const phrase = cutter.push(
        new Float32Array(SAMPLES_PER_FRAME).fill(index),
        typeof level === "number" ? level : level(index)
      )
      if (phrase) phrases.push({ at: index, ...span(phrase) })
    }
  }
  return { cutter, push, phrases }
}

function span(phrase: Float32Array) {
  return {
    first: phrase[0],
    last: phrase[phrase.length - 1],
    frames: phrase.length / SAMPLES_PER_FRAME,
  }
}

describe("phrase endpointing", () => {
  it("ends a phrase at a 700 ms pause after a second of voice, with 450 ms either side", () => {
    const { push, phrases } = feed()

    push(50, QUIET) // frames 0-49
    push(60, VOICE) // 50-109, 1.2 s
    push(34, QUIET) // 110-143, 680 ms
    expect(phrases).toEqual([])
    push(1, QUIET) // 144: the 700th ms

    // 23 frames (460 ms) before the first voiced frame and after the last.
    expect(phrases).toEqual([{ at: 144, first: 27, last: 132, frames: 106 }])
  })

  it("keeps a word or two open across a pause, so it is not sent alone", () => {
    const { push, phrases } = feed()

    push(50, QUIET)
    push(20, VOICE) // 50-69, 0.4 s
    push(50, QUIET) // 70-119, a full second
    expect(phrases).toEqual([])
    push(40, VOICE) // 120-159; 1.2 s of voice in all
    push(35, QUIET) // 160-194

    expect(phrases).toEqual([{ at: 194, first: 27, last: 182, frames: 156 }])
  })

  it("cuts a phrase that reaches 20 s at its quietest 200 ms", () => {
    const { push, phrases } = feed()
    // Speech is never flat: one frame in five falls between syllables.
    const speech = (index: number) => (index % 5 === 0 ? 0.02 : 0.2)

    push(50, QUIET)
    push(750, speech) // 50-799
    push(10, 0.01) // 800-809, a breath too short to end the phrase
    push(217, speech) // 810-1026: the phrase, from frame 27, is 20 s long
    expect(phrases).toEqual([{ at: 1026, first: 27, last: 804, frames: 778 }])

    push(73, speech) // 1027-1099
    push(35, QUIET)
    expect(phrases[1]).toEqual({
      at: 1134,
      first: 805,
      last: 1122,
      frames: 318,
    })
  })

  it("sends a lone word once at 20 s, without the quiet after it, and never the quiet alone", () => {
    const { push, phrases } = feed()

    push(50, QUIET)
    push(20, VOICE) // 50-69, 0.4 s: too short to end at a pause
    push(1500, QUIET) // 70-1569, 30 s of quiet
    expect(phrases).toEqual([{ at: 1026, first: 27, last: 92, frames: 66 }])

    push(60, VOICE) // 1570-1629
    push(35, QUIET)
    // Its own 460 ms before it, not the quiet since the word.
    expect(phrases[1]).toEqual({
      at: 1664,
      first: 1547,
      last: 1652,
      frames: 106,
    })
  })

  it("hands over the phrase in progress when the speaker stops", () => {
    const { cutter, push } = feed()

    push(50, QUIET)
    push(20, VOICE) // 50-69
    push(5, QUIET) // 70-74

    const tail = cutter.flush()
    expect(tail && span(tail)).toEqual({ first: 27, last: 74, frames: 48 })
    expect(cutter.flush()).toBeNull()
  })

  it("has nothing to hand over when no one spoke", () => {
    const { cutter, push } = feed()

    push(100, QUIET)

    expect(cutter.flush()).toBeNull()
  })

  it("hears speech only at three times the room’s noise", () => {
    const { push, phrases } = feed()
    const NOISE = 0.02

    push(200, NOISE) // a fan
    push(60, 0.05) // 2.5 times the fan: not a voice
    push(35, NOISE)
    expect(phrases).toEqual([])

    push(60, 0.08) // four times
    push(35, NOISE)
    expect(phrases).toHaveLength(1)
  })

  it("takes nothing under its minimum for speech, however still the room", () => {
    const { push, phrases, cutter } = feed()

    push(100, 0.0005)
    push(60, 0.004) // eight times the room, still a whisper
    push(35, 0.0005)

    expect(phrases).toEqual([])
    expect(cutter.flush()).toBeNull()
  })
})
