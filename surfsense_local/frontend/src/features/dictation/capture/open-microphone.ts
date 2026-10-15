import { SPEECH_SAMPLE_RATE } from "./resample"

export type MicrophoneFrame = {
  samples: Float32Array
  /** RMS of the samples. */
  level: number
  /** 16 kHz, or the device's rate where a platform refuses that. */
  sampleRate: number
}

export type Microphone = {
  /** Stops every track and closes the context, which clears the OS mic indicator. */
  close: () => void
}

export type OpenMicrophone = (handlers: {
  onFrame: (frame: MicrophoneFrame) => void
  /** The device went away mid-recording. */
  onEnded: () => void
}) => Promise<Microphone>

const CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
}

/** A 16 kHz graph where the platform allows it, else one at the device's rate. */
function graphFor(stream: MediaStream) {
  try {
    const context = new AudioContext({ sampleRate: SPEECH_SAMPLE_RATE })
    try {
      return { context, source: context.createMediaStreamSource(stream) }
    } catch {
      void context.close().catch(() => undefined)
    }
  } catch {
    // Refused outright; the device's rate below.
  }
  const context = new AudioContext()
  return { context, source: context.createMediaStreamSource(stream) }
}

/**
 * The default microphone as 20 ms frames. Errors are getUserMedia's own
 * DOMExceptions; the system's switch being off reads as NotAllowedError.
 */
export const openMicrophone: OpenMicrophone = async ({ onFrame, onEnded }) => {
  // macOS asks the first time; Windows reports its switch; Linux has none.
  const system = await window.surfsense?.microphone?.request()
  if (system === "denied" || system === "restricted") {
    throw new DOMException("Microphone access is off", "NotAllowedError")
  }
  const stream = await navigator.mediaDevices.getUserMedia(CONSTRAINTS)
  let graph: ReturnType<typeof graphFor> | null = null
  try {
    graph = graphFor(stream)
    const { context, source } = graph
    // Resolved by Vite like pdf.js's worker, so it loads over file:// too; a
    // file, never inlined as a data: URL, which is another origin to a worklet.
    await context.audioWorklet.addModule(
      new URL("./frame-worklet.js?no-inline", import.meta.url)
    )
    const node = new AudioWorkletNode(context, "dictation-frames", {
      processorOptions: { frameSamples: Math.round(context.sampleRate * 0.02) },
    })
    node.port.onmessage = (event: MessageEvent<MicrophoneFrame>) =>
      onFrame(event.data)
    source.connect(node)
    // Pulled by the graph only when it reaches the output; it writes silence.
    node.connect(context.destination)
    void context.resume().catch(() => undefined)
    const tracks = stream.getAudioTracks()
    tracks.forEach((track) => track.addEventListener("ended", onEnded))
    return {
      close: () => {
        node.port.onmessage = null
        tracks.forEach((track) => track.removeEventListener("ended", onEnded))
        stream.getTracks().forEach((track) => track.stop())
        source.disconnect()
        node.disconnect()
        void context.close().catch(() => undefined)
      },
    }
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop())
    void graph?.context.close().catch(() => undefined)
    throw error
  }
}
