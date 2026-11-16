import type { MicrophoneFrame, OpenMicrophone } from "./open-microphone"

const VOICE = 0.1
const ROOM = 0.001

/**
 * Stands in for the default microphone: a test says what the speaker does,
 * and the frames reach the composer as the worklet would post them.
 */
export function fakeMicrophone({ sampleRate = 16_000 } = {}) {
  let handlers: Parameters<OpenMicrophone>[0] | null = null
  let refusal: unknown = null
  const state = { open: false, opens: 0, closes: 0 }

  const open: OpenMicrophone = async (next) => {
    if (refusal) throw refusal
    handlers = next
    state.open = true
    state.opens += 1
    return {
      close: () => {
        if (state.open) state.closes += 1
        state.open = false
      },
    }
  }

  const frames = (seconds: number, level: number) => {
    const size = Math.round(sampleRate * 0.02)
    for (let i = 0; i < Math.round(seconds * 50); i++) {
      if (!state.open) return
      const frame: MicrophoneFrame = {
        samples: new Float32Array(size).fill(level),
        level,
        sampleRate,
      }
      handlers?.onFrame(frame)
    }
  }

  return {
    open,
    state,
    /** The next open fails, as getUserMedia would. */
    refuse: (error: unknown) => {
      refusal = error
    },
    /** A phrase: a breath, speech, and the pause that ends it. */
    say: (seconds = 1.2) => {
      frames(0.2, ROOM)
      frames(seconds, VOICE)
      frames(0.7, ROOM)
    },
    /** Speech still going when the speaker stops. */
    speak: (seconds: number) => {
      frames(0.2, ROOM)
      frames(seconds, VOICE)
    },
    quiet: (seconds: number) => frames(seconds, ROOM),
    unplug: () => handlers?.onEnded(),
  }
}
