/**
 * When to start opencode again after it exits, and when to stop until the API
 * asks for the agent again.
 */

const FIRST_DELAY_MS = 10_000
const MAX_DELAY_MS = 5 * 60_000
// A run this long was not a failed start, so the count starts again.
const STAYED_UP_MS = 30_000
const GIVE_UP_AFTER = 3

export type AfterExit = { restartInMs: number } | { gaveUp: string }

export class OpencodeRestarts {
  private startedAt = 0
  private quickExits = 0
  private nextStartAt = 0
  private gaveUpAt: number | null = null

  started(now: number): void {
    this.startedAt = now
  }

  exited(now: number, reason: string): AfterExit {
    if (now - this.startedAt >= STAYED_UP_MS) this.quickExits = 0
    this.quickExits += 1
    if (this.quickExits >= GIVE_UP_AFTER) {
      this.gaveUpAt = now
      return { gaveUp: reason }
    }
    const delay = Math.min(MAX_DELAY_MS, FIRST_DELAY_MS * 2 ** (this.quickExits - 1))
    this.nextStartAt = now + delay
    return { restartInMs: delay }
  }

  /**
   * Whether opencode may start at `now`. Once given up, only a configuration
   * the API wrote since (`askedAt`) earns a start, and one more quick exit
   * gives up again.
   */
  mayStart(now: number, askedAt: number): boolean {
    if (this.gaveUpAt === null) return now >= this.nextStartAt
    if (askedAt <= this.gaveUpAt) return false
    this.gaveUpAt = null
    this.quickExits = GIVE_UP_AFTER - 1
    return true
  }
}
