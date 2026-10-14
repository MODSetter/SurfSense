// Runs on the audio thread: hands the page 20 ms frames, their RMS level and
// the context's rate (`sampleRate`, a global of the worklet scope).
// Plain JavaScript, loaded by URL, so it reaches the AudioWorklet as written.
class DictationFrames extends AudioWorkletProcessor {
  constructor(options) {
    super()
    this.size = options.processorOptions.frameSamples
    this.frame = new Float32Array(this.size)
    this.filled = 0
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (!channel) return true
    let read = 0
    while (read < channel.length) {
      const take = Math.min(channel.length - read, this.size - this.filled)
      this.frame.set(channel.subarray(read, read + take), this.filled)
      this.filled += take
      read += take
      if (this.filled === this.size) {
        let sum = 0
        for (let i = 0; i < this.size; i++) sum += this.frame[i] * this.frame[i]
        const level = Math.sqrt(sum / this.size)
        this.port.postMessage({ samples: this.frame, level, sampleRate }, [
          this.frame.buffer,
        ])
        this.frame = new Float32Array(this.size)
        this.filled = 0
      }
    }
    return true
  }
}

registerProcessor("dictation-frames", DictationFrames)
