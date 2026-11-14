// The week counters, hardware and language, computed by this run's API from
// surfsense.db at read time. It never leaves 127.0.0.1 as anything but buckets.
const SUMMARY_TIMEOUT_MS = 5_000

/** The API's answer as JSON, or null when it is down or answers anything else. */
export async function readLocalSummary(
  apiUrl: string,
  since: Date,
  firstRun: Date,
  fetchFrom: typeof fetch = fetch
): Promise<unknown> {
  // first_run (revision 1.2): no day before it counts as a day used.
  const url =
    `${apiUrl}/usage-statistics/summary?since=${encodeURIComponent(since.toISOString())}` +
    `&first_run=${encodeURIComponent(firstRun.toISOString())}`
  try {
    const reply = await fetchFrom(url, { signal: AbortSignal.timeout(SUMMARY_TIMEOUT_MS) })
    return reply.ok ? await reply.json() : null
  } catch {
    return null
  }
}
