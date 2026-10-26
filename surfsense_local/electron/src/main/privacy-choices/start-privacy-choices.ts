import { totalmem } from "node:os"
import { join } from "node:path"

import { app, ipcMain, session, type BrowserWindow } from "electron"
// Static on purpose: electron-updater is CJS and exposes `autoUpdater` through
// a getter, which `await import()` cannot see (named export comes back
// undefined). require() honours it, and the getter is lazy so dev pays nothing.
import { autoUpdater } from "electron-updater"

import { updatesLocked, updatesLockReason, usageLockReason } from "../admin-policy/policy-locks.ts"
import { readPolicy } from "../admin-policy/read-policy.ts"
import { currentLocale } from "../i18n/app-locale.ts"
import { installChannel } from "../install-channel/install-channel.ts"
import { warnMain } from "../../../../sidecars/session-log/main-warn.ts"
import { sessionLog } from "../../../../sidecars/session-log/session-log.ts"
import { updaterLogger } from "../session-log/updater-log.ts"
import { osLabel, platformLabel } from "../system-labels.ts"
import { channelFile, SURFSENSE_FEED } from "../update-feed/feed-addresses.ts"
import { feedHeaders } from "../update-feed/feed-headers.ts"
import type { ManifestRequest, UpdateFeed } from "../update-feed/latest-manifest.ts"
import { scheduleDailyUpdateCheck, type DailyUpdateCheck } from "../update-schedule/daily-update-check.ts"
import { updateCheckRunner } from "../update-schedule/run-update-check.ts"
import { updaterPendingFolder } from "../updater-cache/pending-folder.ts"
import { tidyUpdaterCache } from "../updater-cache/tidy-updater-cache.ts"
import {
  attachUpdater,
  readUpdatePrefs,
  writeUpdatePrefs,
  type UpdatePrefs,
  type Updates,
  type UpdateState,
} from "../updater.ts"
import { readLocalSummary } from "../usage-statistics/local-summary.ts"
import { privacyStore } from "../usage-statistics/privacy-file.ts"
import { USAGE_ENDPOINT, usageEndpoint } from "../usage-statistics/usage-endpoint.ts"
import { createUsageReporter } from "../usage-statistics/usage-reporter.ts"
import { createPrivacyController, type PrivacyController } from "./privacy-controller.ts"
import { registerPrivacyHandlers } from "./privacy-ipc.ts"
import { registerUpdateHandlers } from "./update-ipc.ts"

// In memory, uncached: no cookie or cache entry ever ties one request to the
// next, and the user agent names no version.
const OUTBOUND_PARTITION = "surfsense-updates-and-usage"
const OUTBOUND_USER_AGENT = "SurfSense"
// An empty list, so Chromium adds no Accept-Language from the system locale.
const NO_ACCEPT_LANGUAGE = ""

/**
 * Update checks, usage statistics and window.surfsense.privacy for this run.
 * Register before the page loads, as the window invokes these at once.
 */
export function startPrivacyChoices(options: {
  apiUrl: string
  mainWindow: () => BrowserWindow | null
}): { stop(): void } {
  const log = (source: string) => (line: string) => sessionLog.append(source, line)
  const policy = readPolicy({ platform: process.platform, env: process.env })
  if (policy.problem) log("policy")(`policy file: ${policy.problem}, so those settings are off`)
  if (updatesLocked(policy)) log("policy")("update checks turned off by policy")
  if (policy.updateFeed) log("policy")(`updates from the mirror ${new URL(policy.updateFeed).host}`)
  const usageLock = usageLockReason(policy)
  if (usageLock) log("policy")(`usage statistics off (${usageLock})`)
  // Packaged only: in dev, execPath and resources are Electron's own, so a
  // Nix-provided Electron would read as a Nix install.
  const channel = app.isPackaged
    ? installChannel({
        platform: process.platform,
        env: process.env,
        execPath: process.execPath,
        resourcesPath: process.resourcesPath,
      })
    : null
  const updatesLock = updatesLockReason(policy, channel)
  if (channel) log("updates")(`updates come from ${channel}, so the app never checks`)

  const userData = app.getPath("userData")
  const prefsPath = join(userData, "updates.json")
  const updatePrefs = (): UpdatePrefs => readUpdatePrefs(prefsPath)
  const saveUpdatePrefs = (prefs: UpdatePrefs) => {
    try {
      writeUpdatePrefs(prefsPath, prefs)
    } catch (error) {
      warnMain(sessionLog, `failed to save update preferences: ${String(error)}`)
    }
  }
  const store = privacyStore(join(userData, "privacy.json"), {
    onWriteError: (error) =>
      warnMain(sessionLog, `failed to save privacy choices: ${String(error)}`),
  })

  const version = app.getVersion()
  const platform = platformLabel(process.platform, process.arch)
  const os = osLabel(process.platform, process.getSystemVersion())
  const outbound = session.fromPartition(OUTBOUND_PARTITION, { cache: false })
  outbound.setUserAgent(OUTBOUND_USER_AGENT, NO_ACCEPT_LANGUAGE)
  const outboundFetch = ((input, init) =>
    outbound.fetch(input instanceof URL ? input.href : input, init)) as typeof fetch

  let controller: PrivacyController
  let lastRequest: ManifestRequest | null = null
  const feed: UpdateFeed = {
    base: policy.updateFeed ?? SURFSENSE_FEED,
    mirror: policy.updateFeed !== null,
    channelFile: channelFile(process.platform, process.arch),
    headers: feedHeaders({ version, platform, os }),
    userAgent: OUTBOUND_USER_AGENT,
    fetch: outboundFetch,
    onRequest: (request) => {
      lastRequest = request
      controller.changed()
    },
    log: log("updates"),
  }

  let updates: Updates
  // A package manager's install never constructs electron-updater, which would
  // pick a DebUpdater from a repackaged deb's package-type.
  if (app.isPackaged && updatesLock !== "channel") {
    autoUpdater.logger = updaterLogger(sessionLog)
    updates = tidyUpdaterCache(
      autoUpdater,
      attachUpdater(
        autoUpdater,
        (state: UpdateState) => options.mainWindow()?.webContents.send("updates:state", state),
        feed
      ),
      {
        pendingFolder: updaterPendingFolder(process.resourcesPath),
        installedVersion: app.getVersion(),
      }
    )
  } else {
    // ponytail: dev has no signed build to update, and a package manager
    // updates its own; expose the same surface so the Settings row renders, and stay idle.
    updates = {
      check: async () => false,
      install: () => undefined,
      state: () => ({ status: "idle" }),
    }
  }

  const check = updateCheckRunner({
    locked: updatesLock,
    channel,
    updates,
    readPrefs: updatePrefs,
    writePrefs: saveUpdatePrefs,
    log: log("updates"),
    onChecked: () => controller.changed(),
  })

  const endpoint = usageEndpoint({ packaged: app.isPackaged, env: process.env })
  const reporter = createUsageReporter({
    store,
    lock: usageLock,
    endpoint,
    facts: { appVersion: version, platform, os },
    summary: (since) => readLocalSummary(options.apiUrl, since),
    locale: currentLocale,
    totalMemoryBytes: totalmem,
    fetch: outboundFetch,
    log: log("usage"),
    onSent: () => controller.changed(),
  })

  let daily: DailyUpdateCheck | null = null
  controller = createPrivacyController({
    policy,
    installChannel: channel,
    store,
    readUpdatePrefs: updatePrefs,
    writeUpdatePrefs: saveUpdatePrefs,
    updates: {
      host: new URL(feed.base).host,
      fallbackHost: feed.mirror ? null : "github.com",
    },
    lastRequest: () => lastRequest,
    usageHost: new URL(endpoint ?? USAGE_ENDPOINT).host,
    reporter,
    checkIfDue: () => void daily?.runIfDue(),
    onChange: (state) => options.mainWindow()?.webContents.send("privacy:state-changed", state),
    log: log("privacy"),
  })

  const isTrusted = (sender: Electron.WebContents): boolean => {
    const window = options.mainWindow()
    return window !== null && sender === window.webContents
  }
  registerUpdateHandlers({
    ipc: ipcMain,
    isTrusted,
    controller,
    updates,
    checkNow: () => void check("manual"),
  })
  registerPrivacyHandlers({ ipc: ipcMain, isTrusted, controller })

  daily = scheduleDailyUpdateCheck({
    automatic: () => controller.updatePrefs().automatic,
    lastAutomaticDay: () => updatePrefs().lastAutomaticDay,
    markAutomaticDay: (day) => saveUpdatePrefs({ ...updatePrefs(), lastAutomaticDay: day }),
    check: () => check("automatic"),
  })
  reporter.start()

  return {
    stop() {
      daily?.stop()
      reporter.stop()
    },
  }
}
