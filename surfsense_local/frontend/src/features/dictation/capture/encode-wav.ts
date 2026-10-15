const HEADER_BYTES = 44

/** Mono 16-bit PCM in a WAV, the only input the transcription server reads. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const view = new DataView(new ArrayBuffer(HEADER_BYTES + samples.length * 2))
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) {
      view.setUint8(offset + i, value.charCodeAt(i))
    }
  }
  text(0, "RIFF")
  view.setUint32(4, 36 + samples.length * 2, true)
  text(8, "WAVE")
  text(12, "fmt ")
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, "data")
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(
      HEADER_BYTES + i * 2,
      sample < 0 ? sample * 0x8000 : sample * 0x7fff,
      true
    )
  }
  return new Blob([view.buffer], { type: "audio/wav" })
}
