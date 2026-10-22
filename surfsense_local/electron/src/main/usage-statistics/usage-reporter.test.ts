import assert from "node:assert/strict"
import test from "node:test"

import type { UsageLockReason } from "../admin-policy/policy-locks.ts"
import { parsePrivacyFile, type PrivacyFile, type PrivacyStore } from "./privacy-file.ts"
import { USAGE_ENDPOINT } from "./usage-endpoint.ts"
import { createUsageReporter } from "./usage-reporter.ts"

const SUMMARY = {
  week: {
    chat_turns: "10-49",
    agent_turns: "0",
    model_source: "local",
    sources: "10-99",
    studio_outputs: "1-4",
    plugin_calls: "0",
    onboarding: "first_answer",
  },
  hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11" },
  ui_language: "en",
}

type Post = { url: string; init: RequestInit }
type Reply = number | "timeout" | "refused"

/** The reporter on a clock and a network the test controls, with privacy.json in memory. */
function reporter(
  options: {
    file?: Partial<PrivacyFile>
    lock?: UsageLockReason | null
    endpoint?: string | null
    summary?: unknown
    locale?: string
    at?: string
    reply?: Reply
  } = {}
) {
  let clock = new Date(options.at ?? "2026-10-21T09:00:00Z")
  let file: PrivacyFile = {
    ...parsePrivacyFile({}, new Date("2026-10-20T08:00:00Z")),
    usageStatistics: true,
    ...options.file,
  }
  const store: PrivacyStore = {
    read: () => file,
    update: (change) => (file = change(file)),
  }
  let reply: Reply = options.reply ?? 204
  const posts: Post[] = []
  const summaries: string[] = []
  const timers: Array<{ kind: "after" | "every"; ms: number }> = []
  let sent = 0
  const usage = createUsageReporter({
    store,
    lock: options.lock ?? null,
    endpoint: options.endpoint === undefined ? USAGE_ENDPOINT : options.endpoint,
    facts: { appVersion: "2.2.4", platform: "win32-x64", os: "windows-11" },
    summary: async (since) => {
      summaries.push(since.toISOString())
      return options.summary === undefined ? SUMMARY : options.summary
    },
    locale: () => options.locale ?? "en",
    totalMemoryBytes: () => 0.98 * 16 * 2 ** 30,
    fetch: (async (input: string | URL | Request, init?: RequestInit) => {
      posts.push({ url: String(input), init: init ?? {} })
      if (reply === "refused") throw new TypeError("fetch failed")
      if (reply === "timeout") throw new DOMException("timed out", "TimeoutError")
      return new Response(null, { status: reply })
    }) as typeof fetch,
    now: () => clock,
    timers: {
      after: (_run, ms) => (timers.push({ kind: "after", ms }), () => undefined),
      every: (_run, ms) => (timers.push({ kind: "every", ms }), () => undefined),
    },
    onSent: () => (sent += 1),
  })
  return {
    usage,
    posts,
    summaries,
    timers,
    sent: () => sent,
    file: () => file,
    bodies: () => posts.map((post) => JSON.parse(String(post.init.body))),
    at: (iso: string) => (clock = new Date(iso)),
    reply: (next: Reply) => (reply = next),
  }
}

test("the first report is the contract's body, key for key, posted as JSON with no cookies", async () => {
  const app = reporter()

  assert.equal(await app.usage.attempt(), "sent")

  assert.equal(app.posts.length, 1)
  const { url, init } = app.posts[0]!
  assert.equal(url, "https://usage.surfsense.com/api/usage")
  assert.equal(init.method, "POST")
  assert.deepEqual(init.headers, { "Content-Type": "application/json" })
  assert.equal(init.credentials, "omit")
  assert.equal(init.redirect, "error")
  const body = app.bodies()[0]
  assert.deepEqual(body, {
    schema: 1,
    app_version: "2.2.4",
    platform: "win32-x64",
    os: "windows-11",
    ui_language: "en",
    install_week: "2026-W43",
    active: { first: true, week: true, month: true },
    hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11" },
    week: {
      chat_turns: "10-49",
      agent_turns: "0",
      model_source: "local",
      sources: "10-99",
      studio_outputs: "1-4",
      plugin_calls: "0",
      onboarding: "first_answer",
    },
  })
  assert.deepEqual(Object.keys(body), [
    "schema",
    "app_version",
    "platform",
    "os",
    "ui_language",
    "install_week",
    "active",
    "hardware",
    "week",
  ])
  // The week block covers the seven days before the report.
  assert.deepEqual(app.summaries, ["2026-10-14T09:00:00.000Z"])
  assert.equal(app.sent(), 1)
  assert.deepEqual(app.file().lastReport, {
    day: "2026-10-21",
    week: "2026-W43",
    month: "2026-10",
  })
  assert.deepEqual(app.file().lastSent, { at: "2026-10-21T09:00:00.000Z", body })
})

test("later reports carry the hardware never again, and the week block once per ISO week", async () => {
  const app = reporter()
  await app.usage.attempt()

  app.at("2026-10-22T09:00:00Z")
  await app.usage.attempt()
  app.at("2026-10-26T09:00:00Z")
  await app.usage.attempt()
  app.at("2026-10-31T09:00:00Z")
  await app.usage.attempt()
  // Sunday 1 Nov is still ISO week 44, but a new month.
  app.at("2026-11-01T09:00:00Z")
  await app.usage.attempt()

  const later = app.bodies().slice(1)
  assert.deepEqual(
    later.map((body) => [body.active, body.hardware, body.week === null]),
    [
      [{ first: false, week: false, month: false }, null, true],
      [{ first: false, week: true, month: false }, null, false],
      [{ first: false, week: false, month: false }, null, true],
      [{ first: false, week: false, month: true }, null, true],
    ]
  )
})

test("at most one report a UTC day is accepted", async () => {
  const app = reporter()

  assert.equal(await app.usage.attempt(), "sent")
  app.at("2026-10-21T23:59:00Z")
  assert.equal(await app.usage.attempt(), "skipped")
  app.at("2026-10-22T00:01:00Z")
  assert.equal(await app.usage.attempt(), "sent")

  assert.equal(app.posts.length, 2)
})

test("three tries a UTC day, across restarts, then nothing until the next day", async () => {
  const app = reporter({ reply: 503 })

  for (const at of ["09:00", "10:00", "11:00", "12:00", "13:00"]) {
    app.at(`2026-10-21T${at}:00Z`)
    await app.usage.attempt()
  }
  assert.equal(app.posts.length, 3)
  assert.deepEqual(app.file().attempts, { day: "2026-10-21", count: 3 })
  assert.equal(app.file().lastSent, null)

  app.reply("timeout")
  app.at("2026-10-22T09:00:00Z")
  assert.equal(await app.usage.attempt(), "failed")
  app.reply("refused")
  assert.equal(await app.usage.attempt(), "failed")
  app.reply(204)
  assert.equal(await app.usage.attempt(), "sent")
  assert.equal(app.posts.length, 6)
  // Still the first accepted report: the failed ones changed nothing.
  assert.equal(app.bodies()[5].active.first, true)
})

const NEVER_SENT: Array<[string, Parameters<typeof reporter>[0]]> = [
  ["switched off", { file: { usageStatistics: false } }],
  ["never asked", { file: { usageStatistics: null } }],
  ["locked off by the admin policy", { lock: "policy" }],
  ["locked off by DO_NOT_TRACK", { lock: "do_not_track" }],
  ["running as a development build", { endpoint: null }],
]

for (const [why, options] of NEVER_SENT) {
  test(`nothing is sent or even read while usage statistics are ${why}`, async () => {
    const app = reporter(options)

    assert.equal(await app.usage.attempt(), "skipped")

    assert.deepEqual(app.posts, [])
    assert.deepEqual(app.summaries, [])
    assert.equal(app.file().attempts, null)
  })
}

test("a development build sends to SURFSENSE_TELEMETRY_DEV_ENDPOINT when one is set", async () => {
  const app = reporter({ endpoint: "http://localhost:3000/api/usage" })

  await app.usage.attempt()

  assert.equal(app.posts[0]!.url, "http://localhost:3000/api/usage")
})

test("whatever the local API answers, only the contract's values leave", async () => {
  const app = reporter({
    summary: {
      week: { chat_turns: "C:\\Users\\ada\\notes.pdf", sources: 12, onboarding: "first_answer", extra: "x" },
      hardware: { ram_gb: "huge", gpu: "NVIDIA RTX 4090", vram_gb: "24+" },
      ui_language: "fr",
      install_id: "abc",
    },
    locale: "ja",
  })

  await app.usage.attempt()

  const body = app.bodies()[0]
  assert.deepEqual(body.week, {
    chat_turns: "unknown",
    agent_turns: "unknown",
    model_source: "unknown",
    sources: "unknown",
    studio_outputs: "unknown",
    plugin_calls: "unknown",
    onboarding: "first_answer",
  })
  // RAM falls back to the main process's own count, rounded to whole GiB.
  assert.deepEqual(body.hardware, { ram_gb: "16-31", gpu: "unknown", vram_gb: "24+" })
  assert.equal(body.ui_language, "ja")
  assert.equal("install_id" in body, false)
})

test("with the local API down the report still goes, with unknowns and the window's language", async () => {
  const app = reporter({ summary: null, locale: "zh-CN" })

  await app.usage.attempt()

  const body = app.bodies()[0]
  assert.equal(body.ui_language, "other")
  assert.equal(body.week.chat_turns, "unknown")
  assert.deepEqual(body.hardware, { ram_gb: "16-31", gpu: "unknown", vram_gb: "unknown" })
})

test("the preview is the next body, built but not sent, even while switched off", async () => {
  const app = reporter({ file: { usageStatistics: null } })

  const preview = await app.usage.preview()

  assert.deepEqual(app.posts, [])
  assert.equal(preview?.schema, 1)
  assert.deepEqual(preview?.active, { first: true, week: true, month: true })
  assert.equal(app.file().attempts, null)
})

test("tries about two minutes after launch, then every hour, and soon after a yes", () => {
  const app = reporter()

  app.usage.start()
  app.usage.nudge()

  assert.deepEqual(app.timers, [
    { kind: "after", ms: 120_000 },
    { kind: "every", ms: 3_600_000 },
    { kind: "after", ms: 120_000 },
  ])
})
