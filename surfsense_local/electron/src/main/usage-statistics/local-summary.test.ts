import assert from "node:assert/strict"
import test from "node:test"

import { readLocalSummary } from "./local-summary.ts"

const API = "http://127.0.0.1:52341"
const SINCE = new Date("2026-10-14T09:00:00Z")

type Answer = Response | Error

/** The local API as the reader sees it, every request kept. */
function api(answer: () => Answer) {
  const requests: Array<{ url: string; init: RequestInit }> = []
  const fetchFrom = (async (input: string | URL | Request, init?: RequestInit) => {
    requests.push({ url: String(input), init: init ?? {} })
    const next = answer()
    if (next instanceof Error) throw next
    return next
  }) as typeof fetch
  return { fetchFrom, requests }
}

test("asks the backend's summary route for the window since the given instant, with a timeout", async () => {
  const summary = { week: { chat_turns: "1-9" }, hardware: null, ui_language: "de" }
  const local = api(() => Response.json(summary))

  assert.deepEqual(await readLocalSummary(API, SINCE, local.fetchFrom), summary)

  assert.equal(local.requests.length, 1)
  assert.equal(
    local.requests[0]!.url,
    "http://127.0.0.1:52341/usage-statistics/summary?since=2026-10-14T09%3A00%3A00.000Z"
  )
  assert.ok(local.requests[0]!.init.signal instanceof AbortSignal)
})

const NO_SUMMARY: Array<[string, () => Answer]> = [
  ["answers 404", () => new Response("Not Found", { status: 404 })],
  ["answers 500", () => Response.json({ week: {} }, { status: 500 })],
  ["answers something that is not JSON", () => new Response("<html>", { status: 200 })],
  ["is down", () => new TypeError("fetch failed")],
  ["does not answer in time", () => new DOMException("timed out", "TimeoutError")],
]

for (const [why, answer] of NO_SUMMARY) {
  test(`no summary when the local API ${why}`, async () => {
    const local = api(answer)

    assert.equal(await readLocalSummary(API, SINCE, local.fetchFrom), null)
  })
}
