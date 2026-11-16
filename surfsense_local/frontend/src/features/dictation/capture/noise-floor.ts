// 3 s of 20 ms frames.
const WINDOW_FRAMES = 150
const PERCENTILE = 0.1

/**
 * The room's level: the 10th percentile of the last 3 s, low enough that the
 * gaps between words keep it below the speaker however steadily they talk.
 */
export function createNoiseFloor() {
  const levels: number[] = []
  return {
    /** Takes one frame's level and answers the floor including it. */
    add(level: number): number {
      levels.push(level)
      if (levels.length > WINDOW_FRAMES) levels.shift()
      const sorted = [...levels].sort((a, b) => a - b)
      return sorted[Math.floor(PERCENTILE * (sorted.length - 1))]
    },
  }
}
