import assert from "node:assert/strict"
import test from "node:test"

import { readPolicy } from "../admin-policy/read-policy.ts"
import type { InstallChannel } from "../install-channel/install-channel.ts"
import type { UpdatePrefs, Updates } from "../updater.ts"
import { parsePrivacyFile, type PrivacyFile } from "../usage-statistics/privacy-file.ts"
import { createPrivacyController, type PrivacyState } from "./privacy-controller.ts"
import { registerPrivacyHandlers } from "./privacy-ipc.ts"
import { registerUpdateHandlers } from "./update-ipc.ts"

type Listener = (event: Electron.IpcMainInvokeEvent, ...args: unknown[]) => unknown
type Sender = "app" | "app subframe" | "other window"

/** The main process with both bridges registered, under a policy file, environment and install channel. */
function mainProcess(
  options: { policy?: object; env?: Record<string, string>; installChannel?: InstallChannel } = {}
) {
  const handlers = new Map<string, Listener>()
  const mainFrame = {}
  const appWindow = { mainFrame } as unknown as Electron.WebContents
  const otherWindow = { mainFrame: {} } as unknown as Electron.WebContents
  let prefs: UpdatePrefs = { automatic: false }
  let file: PrivacyFile = parsePrivacyFile({}, new Date("2026-10-20T08:00:00Z"))
  const pushed: PrivacyState[] = []
  let dueChecks = 0
  let nudges = 0
  let checksNow = 0

  const policy = readPolicy({
    platform: "linux",
    env: options.env ?? {},
    readFile: () => {
      if (!options.policy) throw Object.assign(new Error("ENOENT"), { code: "ENOENT" })
      return JSON.stringify(options.policy)
    },
  })
  const controller = createPrivacyController({
    policy,
    installChannel: options.installChannel ?? null,
    store: { read: () => file, update: (change) => (file = change(file)) },
    readUpdatePrefs: () => prefs,
    writeUpdatePrefs: (next) => (prefs = next),
    updates: { host: "updates.surfsense.com", fallbackHost: "github.com" },
    lastRequest: () => ({
      url: "https://updates.surfsense.com/api/updates/stable-linux.yml",
      headers: { "X-SurfSense-Version": "2.2.4" },
    }),
    usageHost: "usage.surfsense.com",
    reporter: {
      preview: async () => ({ schema: 1 }) as never,
      nudge: () => (nudges += 1),
    },
    checkIfDue: () => (dueChecks += 1),
    onChange: (state) => pushed.push(state),
  })
  const ipc = {
    handle: (channel: string, listener: Listener) => handlers.set(channel, listener),
  } as unknown as Pick<Electron.IpcMain, "handle">
  const isTrusted = (sender: Electron.WebContents) => sender === appWindow
  registerPrivacyHandlers({ ipc, isTrusted, controller })
  const updates: Updates = {
    check: async () => false,
    install: () => undefined,
    state: () => ({ status: "idle" }),
  }
  registerUpdateHandlers({
    ipc,
    isTrusted,
    controller,
    updates,
    checkNow: () => (checksNow += 1),
  })

  const invoke = (channel: string, from: Sender, ...args: unknown[]) => {
    const sender = from === "other window" ? otherWindow : appWindow
    const senderFrame = from === "app" ? mainFrame : {}
    const listener = handlers.get(channel)
    assert.ok(listener, `no handler for ${channel}`)
    return listener({ sender, senderFrame } as unknown as Electron.IpcMainInvokeEvent, ...args)
  }
  return {
    invoke,
    pushed,
    prefs: () => prefs,
    file: () => file,
    dueChecks: () => dueChecks,
    nudges: () => nudges,
    checksNow: () => checksNow,
  }
}

test("the state says where each switch sends, what was sent, and that nothing was asked yet", async () => {
  const app = mainProcess()

  assert.deepEqual(await app.invoke("privacy:state", "app"), {
    updates: {
      automatic: false,
      locked: false,
      lockedReason: null,
      channel: null,
      host: "updates.surfsense.com",
      fallbackHost: "github.com",
      lastCheckedAt: null,
      lastRequest: {
        url: "https://updates.surfsense.com/api/updates/stable-linux.yml",
        headers: { "X-SurfSense-Version": "2.2.4" },
      },
    },
    usageStatistics: {
      enabled: null,
      locked: false,
      lockedReason: null,
      host: "usage.surfsense.com",
      lastSent: null,
    },
    firstRunAsked: false,
  })
})

test("only the app's own window, in its main frame, reads or changes anything", async () => {
  const app = mainProcess()

  for (const from of ["app subframe", "other window"] as const) {
    assert.equal(await app.invoke("privacy:state", from), null)
    assert.equal(await app.invoke("privacy:preview-usage-report", from), null)
    await app.invoke("privacy:set-usage-statistics", from, true)
    await app.invoke("privacy:complete-first-run", from, { updates: true, usageStatistics: true })
  }
  await app.invoke("updates:set-automatic", "other window", true)
  await app.invoke("updates:check", "other window")

  assert.equal(app.file().usageStatistics, null)
  assert.equal(app.file().firstRunAsked, false)
  assert.equal(app.prefs().automatic, false)
  assert.equal(app.checksNow(), 0)
  assert.deepEqual(app.pushed, [])
})

test("the first-run choices are stored together, and a yes starts today's check and a report", async () => {
  const app = mainProcess()

  await app.invoke("privacy:complete-first-run", "app", { updates: true, usageStatistics: true })

  assert.equal(app.prefs().automatic, true)
  assert.equal(app.file().usageStatistics, true)
  assert.equal(app.file().firstRunAsked, true)
  assert.equal(app.dueChecks(), 1)
  assert.equal(app.nudges(), 1)
  assert.equal(app.pushed.at(-1)?.firstRunAsked, true)
})

test("a first-run no is an answer: stored as off, with nothing started", async () => {
  const app = mainProcess()

  await app.invoke("privacy:complete-first-run", "app", { updates: false, usageStatistics: false })
  await app.invoke("privacy:complete-first-run", "app", { updates: "yes" })

  assert.equal(app.prefs().automatic, false)
  assert.equal(app.file().usageStatistics, false)
  assert.equal(app.file().firstRunAsked, true)
  assert.equal(app.dueChecks(), 0)
  assert.equal(app.nudges(), 0)
})

test("each switch is stored and pushed to the window; the updates switch is the updates bridge's own", async () => {
  const app = mainProcess()

  await app.invoke("privacy:set-usage-statistics", "app", true)
  const prefs = await app.invoke("updates:set-automatic", "app", true)

  assert.equal(app.file().usageStatistics, true)
  assert.deepEqual(prefs, { automatic: true })
  assert.equal(app.pushed.length, 2)
  assert.equal(app.pushed[1]?.updates.automatic, true)
  assert.equal(app.pushed[1]?.usageStatistics.enabled, true)
  assert.deepEqual(await app.invoke("privacy:preview-usage-report", "app"), { schema: 1 })
})

test("DO_NOT_TRACK locks usage statistics off, and the switch cannot turn them on", async () => {
  const app = mainProcess({ env: { DO_NOT_TRACK: "1" } })

  await app.invoke("privacy:set-usage-statistics", "app", true)
  await app.invoke("privacy:complete-first-run", "app", { updates: false, usageStatistics: true })

  const state = (await app.invoke("privacy:state", "app")) as PrivacyState
  assert.deepEqual(state.usageStatistics, {
    enabled: false,
    locked: true,
    lockedReason: "do_not_track",
    host: "usage.surfsense.com",
    lastSent: null,
  })
  assert.equal(app.file().usageStatistics, null)
  assert.equal(app.nudges(), 0)
})

test("a policy that turns updates off reads as off and cannot be switched on", async () => {
  const app = mainProcess({ policy: { updates: "off", usageStatistics: "off" } })

  const prefs = await app.invoke("updates:set-automatic", "app", true)
  await app.invoke("privacy:complete-first-run", "app", { updates: true, usageStatistics: true })

  assert.deepEqual(prefs, { automatic: false })
  assert.deepEqual(await app.invoke("updates:prefs", "app"), { automatic: false })
  const state = (await app.invoke("privacy:state", "app")) as PrivacyState
  assert.equal(state.updates.locked, true)
  assert.equal(state.updates.lockedReason, "policy")
  assert.equal(state.updates.channel, null)
  assert.equal(state.updates.automatic, false)
  assert.equal(state.usageStatistics.lockedReason, "policy")
  assert.equal(app.dueChecks(), 0)
})

test("an install a package manager owns reads as off, cannot be switched on, and says which", async () => {
  const app = mainProcess({ installChannel: "snap" })

  const prefs = await app.invoke("updates:set-automatic", "app", true)
  await app.invoke("privacy:complete-first-run", "app", { updates: true, usageStatistics: false })

  assert.deepEqual(prefs, { automatic: false })
  assert.deepEqual(await app.invoke("updates:prefs", "app"), { automatic: false })
  const state = (await app.invoke("privacy:state", "app")) as PrivacyState
  assert.equal(state.updates.locked, true)
  assert.equal(state.updates.lockedReason, "channel")
  assert.equal(state.updates.channel, "snap")
  assert.equal(state.usageStatistics.locked, false)
  assert.equal(app.dueChecks(), 0)
})

test("a policy that turns updates off names itself, not the channel, as the lock", async () => {
  const app = mainProcess({ policy: { updates: "off" }, installChannel: "apt" })

  const state = (await app.invoke("privacy:state", "app")) as PrivacyState
  assert.equal(state.updates.lockedReason, "policy")
  assert.equal(state.updates.channel, null)
})
