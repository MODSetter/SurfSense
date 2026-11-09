/**
 * A host's stop, run once however often it is asked for. Every caller waits for
 * that one stop: the sidecars run in process groups of their own, so a host that
 * exits before they stop leaves them running.
 */
export function stopOnce(stop: () => Promise<void>): () => Promise<void> {
  let stopping: Promise<void> | null = null
  return () => (stopping ??= stop())
}
