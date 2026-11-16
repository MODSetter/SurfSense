export const SPEECH_SAMPLE_RATE = 16_000

/**
 * A phrase captured at the device's rate, at the 16 kHz the model takes. Only
 * where a platform refuses a 16 kHz AudioContext; elsewhere Chromium resamples.
 */
export async function resampleForSpeech(
  samples: Float32Array,
  sampleRate: number
): Promise<Float32Array> {
  if (sampleRate === SPEECH_SAMPLE_RATE) return samples
  const length = Math.ceil((samples.length * SPEECH_SAMPLE_RATE) / sampleRate)
  const context = new OfflineAudioContext(1, length, SPEECH_SAMPLE_RATE)
  const buffer = context.createBuffer(1, samples.length, sampleRate)
  buffer.copyToChannel(new Float32Array(samples), 0)
  const source = context.createBufferSource()
  source.buffer = buffer
  source.connect(context.destination)
  source.start()
  const rendered = await context.startRendering()
  return rendered.getChannelData(0)
}
