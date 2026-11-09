// Slows password guessing: five failures from one client within a minute, and
// that client waits out the minute (ADR 0074). Held in memory; a restart forgets.
const LIMIT = 5
const WINDOW_MS = 60_000

export class GuessLimit {
  private failures = new Map<string, number[]>()

  /** Seconds the client must wait before guessing again, or 0. */
  waitSeconds(client: string, now: number): number {
    const recent = this.recent(client, now)
    if (recent.length < LIMIT) return 0
    return Math.ceil((recent[0] + WINDOW_MS - now) / 1000)
  }

  failed(client: string, now: number): void {
    this.failures.set(client, [...this.recent(client, now), now])
  }

  succeeded(client: string): void {
    this.failures.delete(client)
  }

  private recent(client: string, now: number): number[] {
    return (this.failures.get(client) ?? []).filter((at) => now - at < WINDOW_MS)
  }
}
