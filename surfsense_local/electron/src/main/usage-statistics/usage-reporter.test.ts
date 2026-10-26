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
  hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11", gpu_runtime: "reachable" },
  ui_language: "en",
}
// A card the OS sees but the model runtime cannot reach.
const UNREACHABLE_GPU = { ram_gb: "16-31", gpu: "nvidia", vram_gb: "unknown", gpu_runtime: "unreachable" }
const NO_FLAGS = { first: false, week: false, month: false }
const BODY_KEYS = [
  "schema",
  "app_version",
  "platform",
  "os",
  "ui_language",
  "install_week",
  "trigger",
  "active",
  "hardware",
  "week",
]

/** The summary as the local API answers it once setup reached `onboarding`. */
function atStep(onboarding: string, hardware: object = SUMMARY.hardware) {
  return { ...SUMMARY, week: { ...SUMMARY.week, onboarding }, hardware }
}

type Post = { url: string; init: RequestInit }
type Reply = number | "timeout" | "refused"
type Timer = { kind: "after" | "every"; ms: number; run: () => void; cancelled: boolean }

/** Lets every pending promise of the fakes below settle. */
const settle = () => new Promise<void>((resolve) => setImmediate(resolve))

/**
 * The reporter on a clock and a network the test controls, with privacy.json in
 * memory. The install first ran at 2026-10-20T08:00Z, so its first week ends
 * at 2026-10-27T08:00Z.
 */
function reporter(
  options: {
    file?: Partial<PrivacyFile>
    lock?: UsageLockReason | null
    endpoint?: string | null
    summary?: unknown
    /** Holds the local API's answer until it resolves. */
    summaryGate?: Promise<void>
    locale?: string
    at?: string
    reply?: Reply
    appVersion?: string
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
  let summary: unknown = options.summary === undefined ? SUMMARY : options.summary
  const posts: Post[] = []
  const summaries: string[] = []
  const timers: Timer[] = []
  const schedule = (kind: Timer["kind"]) => (run: () => void, ms: number) => {
    const timer: Timer = { kind, ms, run, cancelled: false }
    timers.push(timer)
    return () => {
      timer.cancelled = true
    }
  }
  let sent = 0
  const usage = createUsageReporter({
    store,
    lock: options.lock ?? null,
    endpoint: options.endpoint === undefined ? USAGE_ENDPOINT : options.endpoint,
    facts: { appVersion: options.appVersion ?? "2.2.4", platform: "win32-x64", os: "windows-11" },
    summary: async (since) => {
      summaries.push(since.toISOString())
      await options.summaryGate
      if (summary instanceof Error) throw summary
      return summary
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
    timers: { after: schedule("after"), every: schedule("every") },
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
    summary: (next: unknown) => (summary = next),
    choose: (usageStatistics: boolean) => (file = { ...file, usageStatistics }),
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
    trigger: "daily",
    active: { first: true, week: true, month: true },
    hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11", gpu_runtime: "reachable" },
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
  assert.deepEqual(Object.keys(body), BODY_KEYS)
  assert.deepEqual(Object.keys(body.hardware), ["ram_gb", "gpu", "vram_gb", "gpu_runtime"])
  // In the first week the counts cover the time since the first run.
  assert.deepEqual(app.summaries, ["2026-10-20T08:00:00.000Z"])
  assert.equal(app.sent(), 1)
  assert.deepEqual(app.file().lastReport, {
    day: "2026-10-21",
    week: "2026-W43",
    month: "2026-10",
  })
  assert.deepEqual(app.file().lastSent, { at: "2026-10-21T09:00:00.000Z", body })
})

test("in the first week every daily report carries the week, counted since the first run", async () => {
  const app = reporter()

  for (const at of [
    "2026-10-21T09:00:00Z",
    "2026-10-22T09:00:00Z",
    "2026-10-25T09:00:00Z",
    "2026-10-27T07:59:00Z",
  ]) {
    app.at(at)
    assert.equal(await app.usage.attempt(), "sent")
  }

  assert.deepEqual(
    app.bodies().map((body) => [body.trigger, body.active.week, body.week?.onboarding]),
    [
      ["daily", true, "first_answer"],
      ["daily", false, "first_answer"],
      ["daily", false, "first_answer"],
      ["daily", true, "first_answer"],
    ]
  )
  assert.deepEqual(app.summaries, Array(4).fill("2026-10-20T08:00:00.000Z"))
})

test("after the first week the week block comes once per ISO week, covering the seven days before", async () => {
  const app = reporter()
  await app.usage.attempt()

  for (const at of [
    "2026-10-27T09:00:00Z",
    "2026-10-28T09:00:00Z",
    "2026-10-31T09:00:00Z",
    // Sunday 1 Nov is still ISO week 44, but a new month.
    "2026-11-01T09:00:00Z",
  ]) {
    app.at(at)
    await app.usage.attempt()
  }

  const later = app.bodies().slice(1)
  assert.deepEqual(
    later.map((body) => [body.active, body.hardware, body.week === null]),
    [
      [{ first: false, week: true, month: false }, null, false],
      [{ first: false, week: false, month: false }, null, true],
      [{ first: false, week: false, month: false }, null, true],
      [{ first: false, week: false, month: true }, null, true],
    ]
  )
  assert.equal(app.summaries[1], "2026-10-20T09:00:00.000Z")
})

test("in the first week the hardware goes again only while part of it was unknown, and only when it changed", async () => {
  const app = reporter({ summary: atStep("first_answer", UNREACHABLE_GPU) })

  await app.usage.attempt()
  app.at("2026-10-22T09:00:00Z")
  await app.usage.attempt()
  // The runtime reaches the card now: sent once more, then no longer.
  app.summary(SUMMARY)
  app.at("2026-10-23T09:00:00Z")
  await app.usage.attempt()
  app.at("2026-10-24T09:00:00Z")
  await app.usage.attempt()
  app.summary(atStep("first_answer", UNREACHABLE_GPU))
  app.at("2026-10-25T09:00:00Z")
  await app.usage.attempt()

  assert.deepEqual(
    app.bodies().map((body) => body.hardware),
    // Day two repeats day one's block, so it is left out; the fixed card is sent.
    [UNREACHABLE_GPU, null, SUMMARY.hardware, null, null]
  )
})

test("after the first week the hardware is never sent again, however unknown", async () => {
  const app = reporter({ summary: atStep("first_answer", UNREACHABLE_GPU) })

  await app.usage.attempt()
  app.at("2026-10-28T09:00:00Z")
  await app.usage.attempt()

  assert.equal(app.bodies()[1].hardware, null)
})

test("a setup report goes once for each new setup step, with every flag false and the week's counts", async () => {
  const app = reporter({ summary: atStep("not_started") })
  await app.usage.attempt()

  app.summary(atStep("model_chosen"))
  app.at("2026-10-21T09:05:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")
  app.at("2026-10-21T09:10:00Z")
  assert.equal(await app.usage.checkSetup(), "skipped")
  // Steps reached between two checks make one report.
  app.summary(atStep("first_answer"))
  app.at("2026-10-21T09:15:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")
  app.at("2026-10-21T09:20:00Z")
  assert.equal(await app.usage.checkSetup(), "skipped")

  const setup = app.bodies().slice(1)
  assert.deepEqual(
    setup.map((body) => [body.trigger, body.active, body.week.onboarding, body.hardware]),
    [
      ["setup", NO_FLAGS, "model_chosen", null],
      ["setup", NO_FLAGS, "first_answer", null],
    ]
  )
  assert.deepEqual(Object.keys(setup[0]), BODY_KEYS)
  assert.deepEqual(setup[0].week, { ...SUMMARY.week, onboarding: "model_chosen" })
  assert.equal(app.posts[1]!.init.credentials, "omit")
  assert.equal(app.posts[1]!.init.redirect, "error")
  assert.equal(app.file().onboardingReported, "first_answer")
  assert.deepEqual(app.file().lastSent, { at: "2026-10-21T09:15:00.000Z", body: setup[1] })
  assert.equal(app.sent(), 3)
})

test("a setup report leaves the day's report and its tries alone", async () => {
  const app = reporter({ summary: atStep("not_started") })
  await app.usage.attempt()

  app.summary(atStep("model_ready"))
  app.at("2026-10-22T08:00:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")

  assert.deepEqual(app.file().lastReport, { day: "2026-10-21", week: "2026-W43", month: "2026-10" })
  assert.deepEqual(app.file().attempts, { day: "2026-10-21", count: 1 })
  app.at("2026-10-22T09:00:00Z")
  assert.equal(await app.usage.attempt(), "sent")
  assert.equal(app.bodies()[2].trigger, "daily")
  assert.deepEqual(app.file().attempts, { day: "2026-10-22", count: 1 })
})

test("a setup step counts as reported only once a report carrying it is accepted", async () => {
  const app = reporter({ summary: atStep("model_chosen"), reply: 503 })

  assert.equal(await app.usage.checkSetup(), "failed")
  app.reply("timeout")
  app.at("2026-10-21T10:00:00Z")
  assert.equal(await app.usage.checkSetup(), "failed")
  assert.equal(app.file().onboardingReported, null)
  assert.equal(app.file().lastSent, null)
  assert.equal(app.sent(), 0)

  app.reply(204)
  app.at("2026-10-21T11:00:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")
  assert.equal(app.file().onboardingReported, "model_chosen")
  assert.equal(await app.usage.checkSetup(), "skipped")
  assert.equal(app.posts.length, 3)
  assert.equal(app.file().attempts, null)
})

test("a setup step not accepted is tried three times a UTC day, an hour apart, across restarts", async () => {
  const app = reporter({ summary: atStep("model_chosen"), reply: 503 })

  assert.equal(await app.usage.checkSetup(), "failed")
  app.at("2026-10-21T09:55:00Z")
  assert.equal(await app.usage.checkSetup(), "skipped")
  app.at("2026-10-21T10:00:00Z")
  assert.equal(await app.usage.checkSetup(), "failed")
  const restarted = reporter({
    file: app.file(),
    summary: atStep("model_chosen"),
    reply: "timeout",
    at: "2026-10-21T10:30:00Z",
  })
  assert.equal(await restarted.usage.checkSetup(), "skipped")
  restarted.at("2026-10-21T11:00:00Z")
  assert.equal(await restarted.usage.checkSetup(), "failed")
  restarted.at("2026-10-21T23:59:00Z")
  assert.equal(await restarted.usage.checkSetup(), "skipped")
  assert.equal(app.posts.length + restarted.posts.length, 3)

  restarted.reply(204)
  restarted.at("2026-10-22T00:00:00Z")
  assert.equal(await restarted.usage.checkSetup(), "sent")
  assert.equal(restarted.file().onboardingReported, "model_chosen")
  // The daily report's own tries are untouched.
  assert.equal(restarted.file().attempts, null)
})

test("a setup report the endpoint refuses with a 4xx is not tried again that UTC day", async () => {
  const app = reporter({ summary: atStep("model_chosen"), reply: 400 })

  assert.equal(await app.usage.checkSetup(), "failed")
  app.reply(204)
  for (const at of ["10:00", "16:00", "23:55"]) {
    app.at(`2026-10-21T${at}:00Z`)
    assert.equal(await app.usage.checkSetup(), "skipped")
  }
  app.at("2026-10-22T00:00:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")

  assert.equal(app.posts.length, 2)
})

test("a later setup step gets its own tries", async () => {
  const app = reporter({ summary: atStep("model_chosen"), reply: 429 })
  await app.usage.checkSetup()

  app.summary(atStep("model_ready"))
  app.reply(204)
  app.at("2026-10-21T09:05:00Z")
  assert.equal(await app.usage.checkSetup(), "sent")

  assert.deepEqual(
    app.bodies().map((body) => body.week.onboarding),
    ["model_chosen", "model_ready"]
  )
})

const FAILING_DAY: Array<[Reply, number]> = [
  [503, 3],
  ["timeout", 3],
  [400, 1],
]

for (const [reply, posts] of FAILING_DAY) {
  test(`a day of five-minute checks against an endpoint answering ${reply} sends ${posts} setup report(s)`, async () => {
    const app = reporter({
      file: { lastReport: { day: "2026-10-21", week: "2026-W43", month: "2026-10" } },
      summary: atStep("model_chosen"),
      reply,
      at: "2026-10-21T00:00:00Z",
    })
    app.usage.start()
    const check = app.timers.find((timer) => timer.ms === 300_000)!

    for (let minute = 0; minute < 24 * 60; minute += 5) {
      app.at(new Date(Date.parse("2026-10-21T00:00:00Z") + minute * 60_000).toISOString())
      check.run()
      await settle()
    }

    assert.equal(app.posts.length, posts)
  })
}

test("a step a daily report carried already sends no setup report", async () => {
  const app = reporter({ summary: atStep("first_source") })
  await app.usage.attempt()

  app.at("2026-10-21T09:05:00Z")
  assert.equal(await app.usage.checkSetup(), "skipped")

  assert.equal(app.posts.length, 1)
  assert.equal(app.file().onboardingReported, "first_source")
})

const NO_STEP: Array<[string, unknown]> = [
  ["the local API is down", null],
  ["setup's step is unknown", atStep("unknown")],
  ["setup has not started", atStep("not_started")],
  ["the step is not one of the contract's", atStep("C:\\Users\\ada")],
]

for (const [why, summary] of NO_STEP) {
  test(`no setup report while ${why}`, async () => {
    const app = reporter({ summary })

    assert.equal(await app.usage.checkSetup(), "skipped")

    assert.deepEqual(app.posts, [])
    assert.equal(app.file().onboardingReported, null)
  })
}

test("once setup's last step is reported, the check reads nothing more", async () => {
  const app = reporter({ summary: atStep("first_answer") })
  assert.equal(await app.usage.checkSetup(), "sent")
  const reads = app.summaries.length

  app.at("2026-10-21T10:00:00Z")
  assert.equal(await app.usage.checkSetup(), "skipped")
  assert.equal(app.summaries.length, reads)
})

test("setup reports stop when the first week ends, without reading anything", async () => {
  const lastMoment = reporter({ summary: atStep("model_chosen"), at: "2026-10-27T07:59:59Z" })
  assert.equal(await lastMoment.usage.checkSetup(), "sent")

  const after = reporter({ summary: atStep("model_chosen"), at: "2026-10-27T08:00:00Z" })
  assert.equal(await after.usage.checkSetup(), "skipped")
  assert.deepEqual(after.summaries, [])
  assert.deepEqual(after.posts, [])
})

test("a setup report in the first week carries the hardware again while part of it was unknown", async () => {
  const app = reporter({ summary: atStep("not_started", UNREACHABLE_GPU) })
  await app.usage.attempt()

  app.summary(atStep("model_chosen"))
  app.at("2026-10-21T09:05:00Z")
  await app.usage.checkSetup()
  app.summary(atStep("model_ready"))
  app.at("2026-10-21T09:10:00Z")
  await app.usage.checkSetup()

  assert.deepEqual(
    app.bodies().map((body) => body.hardware),
    [UNREACHABLE_GPU, SUMMARY.hardware, null]
  )
})

test("a setup report before any daily one carries no hardware", async () => {
  const app = reporter({ summary: atStep("model_chosen") })

  await app.usage.checkSetup()
  await app.usage.attempt()

  assert.deepEqual(
    app.bodies().map((body) => [body.trigger, body.active.first, body.hardware !== null]),
    [
      ["setup", false, false],
      ["daily", true, true],
    ]
  )
})

test("a setup check waits out a daily report in flight", async () => {
  let answer = () => undefined as void
  const app = reporter({
    summary: atStep("model_chosen"),
    summaryGate: new Promise<void>((resolve) => (answer = resolve)),
  })

  const daily = app.usage.attempt()
  assert.equal(await app.usage.checkSetup(), "skipped")
  answer()
  assert.equal(await daily, "sent")

  assert.equal(app.summaries.length, 1)
  assert.equal(app.posts.length, 1)
})

test("a no given while a setup report is being built stops it before it is sent", async () => {
  let answer = () => undefined as void
  const app = reporter({
    summary: atStep("model_chosen"),
    summaryGate: new Promise<void>((resolve) => (answer = resolve)),
  })

  const pending = app.usage.checkSetup()
  app.choose(false)
  answer()

  assert.equal(await pending, "skipped")
  assert.deepEqual(app.posts, [])
  assert.equal(app.file().onboardingReported, null)
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
    const app = reporter({ ...options, summary: atStep("model_chosen") })

    assert.equal(await app.usage.attempt(), "skipped")
    assert.equal(await app.usage.checkSetup(), "skipped")

    assert.deepEqual(app.posts, [])
    assert.deepEqual(app.summaries, [])
    assert.equal(app.file().attempts, null)
  })
}

test("a no given while a report is being built stops it before it is sent", async () => {
  let answer = () => undefined as void
  const app = reporter({ summaryGate: new Promise<void>((resolve) => (answer = resolve)) })

  const pending = app.usage.attempt()
  app.choose(false)
  answer()

  assert.equal(await pending, "skipped")
  assert.deepEqual(app.posts, [])
  assert.equal(app.file().lastSent, null)
  assert.equal(app.sent(), 0)
})

test("no report over 4 KB leaves, daily or setup", async () => {
  const app = reporter({ summary: atStep("model_chosen"), appVersion: "9".repeat(4096) })

  assert.equal(await app.usage.attempt(), "failed")
  assert.equal(await app.usage.checkSetup(), "failed")

  assert.deepEqual(app.posts, [])
  // The largest body the contract allows stays well under the cap.
  const largest = (await reporter({ summary: atStep("first_answer", UNREACHABLE_GPU) }).usage.preview())!
  assert.ok(Buffer.byteLength(JSON.stringify(largest)) < 1024)
})

test("a summary that cannot be read fails the try, daily or setup, and never escapes", async () => {
  const app = reporter({ summary: new Error("database is locked") })

  assert.equal(await app.usage.attempt(), "failed")
  assert.equal(await app.usage.checkSetup(), "failed")

  assert.deepEqual(app.posts, [])
})

test("a development build sends to SURFSENSE_TELEMETRY_DEV_ENDPOINT when one is set", async () => {
  const app = reporter({ endpoint: "http://localhost:3000/api/usage" })

  await app.usage.attempt()

  assert.equal(app.posts[0]!.url, "http://localhost:3000/api/usage")
})

test("whatever the local API answers, only the contract's values leave", async () => {
  const app = reporter({
    summary: {
      week: { chat_turns: "C:\\Users\\ada\\notes.pdf", sources: 12, onboarding: "first_answer", extra: "x" },
      hardware: { ram_gb: "huge", gpu: "NVIDIA RTX 4090", vram_gb: "24+", gpu_runtime: "CUDA 12" },
      ui_language: "fr",
      install_id: "abc",
      trigger: "setup",
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
  assert.deepEqual(body.hardware, {
    ram_gb: "16-31",
    gpu: "unknown",
    vram_gb: "24+",
    gpu_runtime: "unknown",
  })
  assert.equal(body.ui_language, "ja")
  assert.equal(body.trigger, "daily")
  assert.equal("install_id" in body, false)
})

test("with the local API down the report still goes, with unknowns and the window's language", async () => {
  const app = reporter({ summary: null, locale: "zh-CN" })

  await app.usage.attempt()

  const body = app.bodies()[0]
  assert.equal(body.ui_language, "other")
  assert.equal(body.week.chat_turns, "unknown")
  assert.deepEqual(body.hardware, {
    ram_gb: "16-31",
    gpu: "unknown",
    vram_gb: "unknown",
    gpu_runtime: "unknown",
  })
})

test("the preview is the next daily body, built but not sent, even while switched off", async () => {
  const app = reporter({ file: { usageStatistics: null }, summary: atStep("model_chosen") })

  const preview = await app.usage.preview()

  assert.deepEqual(app.posts, [])
  assert.equal(preview?.schema, 1)
  assert.equal(preview?.trigger, "daily")
  assert.deepEqual(preview?.active, { first: true, week: true, month: true })
  assert.equal(preview?.week?.onboarding, "model_chosen")
  assert.equal(app.file().attempts, null)
})

test("tries two minutes after launch, then hourly, checks setup every five minutes in the first week, and soon after a yes", () => {
  const app = reporter()

  app.usage.start()
  app.usage.nudge()

  assert.deepEqual(
    app.timers.map(({ kind, ms }) => ({ kind, ms })),
    [
      { kind: "after", ms: 120_000 },
      { kind: "every", ms: 3_600_000 },
      { kind: "every", ms: 300_000 },
      { kind: "after", ms: 120_000 },
    ]
  )
  app.usage.stop()
  assert.ok(app.timers.every((timer) => timer.cancelled))
})

test("after the first week no setup check is scheduled", () => {
  const app = reporter({ at: "2026-10-27T08:00:00Z" })

  app.usage.start()

  assert.deepEqual(
    app.timers.map(({ kind, ms }) => ({ kind, ms })),
    [
      { kind: "after", ms: 120_000 },
      { kind: "every", ms: 3_600_000 },
    ]
  )
})

test("the five-minute check reports a new step, and stops itself once the first week is over", async () => {
  const app = reporter({
    file: { lastReport: { day: "2026-10-21", week: "2026-W43", month: "2026-10" } },
    summary: atStep("model_chosen"),
  })
  app.usage.start()
  const check = app.timers.find((timer) => timer.ms === 300_000)!

  check.run()
  await settle()
  assert.deepEqual(app.bodies().map((body) => body.trigger), ["setup"])

  app.summary(atStep("model_ready"))
  app.at("2026-10-27T08:00:00Z")
  check.run()
  await settle()
  assert.equal(app.posts.length, 1)
  assert.equal(app.summaries.length, 1)
  assert.equal(check.cancelled, true)
})

test("after a yes, the day's report goes first, then the setup check", async () => {
  const app = reporter({
    file: {
      usageStatistics: false,
      lastReport: { day: "2026-10-21", week: "2026-W43", month: "2026-10" },
      onboardingReported: "not_started",
    },
    summary: atStep("model_ready"),
  })
  app.choose(true)

  app.usage.nudge()
  app.timers[0]!.run()
  await settle()

  // Today's report went before the no, so the yes sends only the new step.
  assert.deepEqual(
    app.bodies().map((body) => [body.trigger, body.week.onboarding]),
    [["setup", "model_ready"]]
  )
})
