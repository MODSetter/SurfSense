// The agent checks a Word document it made by looking at its pages, and the app
// has no Word converter: Electron lays the file out with the in-app viewer's
// library and prints it. The API queues each request and waits; Electron polls
// for them, as it polls for the image runtime, so the API needs no way in here.
// Every call carries the key Electron handed the API at launch: any process on
// the machine can reach loopback, and only Electron may take or answer a request.

const ROUTES = "/agent/previews/docx-snapshots"

// Someone is waiting on a tool call, so faster than the image runtime's 5 s.
const POLL_MS = 2000
// Under the API's own 30 s wait, which starts when the request is queued: a
// request is taken within a poll, so a slow print is reported rather than lost.
const PRINT_MS = 25_000
// A loopback call answers in milliseconds, uploads included; one that has not
// in this time is stuck, and waiting on it would stop polling.
const REQUEST_MS = 10_000
// Each print is a hidden window with its own renderer process. Requests come from
// agent threads rendering at the same moment, which is a few at most.
const PRINTS_AT_ONCE = 3
// The API's limit on a failure's reason.
const REASON_CHARS = 500

/** Lay out the Word file at `fileUrl` and print it; stop when `signal` aborts. */
export type PrintDocx = (fileUrl: string, signal: AbortSignal) => Promise<Uint8Array>

type SnapshotRequest = { id: string; file_url: string }

type Api = { url: string; authorization: string; requestMs: number }

/** Poll the API for Word documents to print until the returned stop is called. */
export function serveDocxSnapshots(options: {
  apiUrl: string
  /** The snapshot key the API was started with (SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY). */
  key: string
  print: PrintDocx
  pollMs?: number
  printMs?: number
  requestMs?: number
}): () => void {
  const {
    apiUrl,
    key,
    print,
    pollMs = POLL_MS,
    printMs = PRINT_MS,
    requestMs = REQUEST_MS,
  } = options
  const api: Api = { url: apiUrl, authorization: `Bearer ${key}`, requestMs }
  let stopped = false
  let timer: NodeJS.Timeout | undefined
  let printing = 0

  const tick = async (): Promise<void> => {
    let took = false
    if (printing < PRINTS_AT_ONCE) {
      try {
        const request = await takeNext(api)
        if (request) {
          took = true
          printing += 1
          // Not awaited: a request queued behind a slow print would outlive the API's wait.
          void serve(api, request, print, printMs)
            .catch(() => {
              // The API is down or restarting; its waiter gives up on its own.
            })
            .finally(() => {
              printing -= 1
            })
        }
      } catch {
        // The API is down, restarting or stuck; the next tick tries again.
      }
    }
    if (stopped) return
    // Another request may be waiting right behind the one just taken.
    timer = setTimeout(() => void tick(), took ? 0 : pollMs)
    timer.unref()
  }
  void tick()

  return () => {
    stopped = true
    clearTimeout(timer)
  }
}

async function takeNext(api: Api): Promise<SnapshotRequest | null> {
  const reply = await fetch(`${api.url}${ROUTES}/next`, {
    headers: { authorization: api.authorization },
    signal: AbortSignal.timeout(api.requestMs),
  })
  if (reply.status !== 200) return null
  return (await reply.json()) as SnapshotRequest
}

async function serve(
  api: Api,
  request: SnapshotRequest,
  print: PrintDocx,
  printMs: number,
): Promise<void> {
  const answer = `${api.url}${ROUTES}/${encodeURIComponent(request.id)}`
  const fail = (reason: string) =>
    fetch(`${answer}/failure`, {
      method: "POST",
      headers: { authorization: api.authorization, "content-type": "application/json" },
      body: JSON.stringify({ reason: reason.slice(0, REASON_CHARS) || "unknown error" }),
      signal: AbortSignal.timeout(api.requestMs),
    })

  const signal = AbortSignal.timeout(printMs)
  // A window torn down mid-print may never settle its calls; the time box holds anyway.
  const timedOut = new Promise<never>((_resolve, reject) =>
    signal.addEventListener("abort", () => reject(signal.reason), { once: true }),
  )
  // Fires after a print that finished in time too, when no one awaits it.
  timedOut.catch(() => {})
  let pdf: Uint8Array
  try {
    pdf = await Promise.race([print(new URL(request.file_url, api.url).href, signal), timedOut])
  } catch (error) {
    await fail(
      signal.aborted
        ? `the document did not lay out and print within ${printMs / 1000} s`
        : error instanceof Error
          ? error.message
          : String(error),
    )
    return
  }
  const delivered = await fetch(`${answer}/pdf`, {
    method: "POST",
    headers: { authorization: api.authorization, "content-type": "application/pdf" },
    body: pdf,
    signal: AbortSignal.timeout(api.requestMs),
  })
  // 404: no one waits for it any more. Any other refusal would leave the waiter
  // sitting out its full time with no reason.
  if (delivered.ok || delivered.status === 404) return
  await fail(
    delivered.status === 413
      ? "the printed document is too large to preview"
      : `the API refused the printed document (HTTP ${delivered.status})`,
  )
}
