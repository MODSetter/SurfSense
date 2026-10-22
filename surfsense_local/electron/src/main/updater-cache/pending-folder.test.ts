import assert from "node:assert/strict"
import { mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { updaterPendingFolder } from "./pending-folder.ts"

const NAME = "surfsense-local-electron-updater"

function resources(yml: string | null): string {
  const dir = mkdtempSync(join(tmpdir(), "resources-"))
  if (yml !== null) writeFileSync(join(dir, "app-update.yml"), yml)
  return dir
}

const appUpdateYml = [
  "owner: MODSetter",
  "repo: SurfSense",
  "provider: github",
  "channel: stable",
  `updaterCacheDirName: ${NAME}`,
  "publisherName:",
  "  - SurfSense",
  "",
].join("\n")

test("on Windows it is the folder electron-updater names, under LOCALAPPDATA", () => {
  const found = updaterPendingFolder(resources(appUpdateYml), {
    platform: "win32",
    env: { LOCALAPPDATA: "C:\\Users\\a\\AppData\\Local" },
    home: "C:\\Users\\a",
  })
  assert.equal(found, join("C:\\Users\\a\\AppData\\Local", NAME, "pending"))
})

test("on Windows without LOCALAPPDATA it falls back as electron-updater does", () => {
  const found = updaterPendingFolder(resources(appUpdateYml), {
    platform: "win32",
    env: {},
    home: "C:\\Users\\a",
  })
  assert.equal(found, join("C:\\Users\\a", "AppData", "Local", NAME, "pending"))
})

test("on macOS it sits in the user's Caches", () => {
  const found = updaterPendingFolder(resources(appUpdateYml), {
    platform: "darwin",
    env: { XDG_CACHE_HOME: "/ignored" },
    home: "/Users/a",
  })
  assert.equal(found, join("/Users/a", "Library", "Caches", NAME, "pending"))
})

test("on Linux it honours XDG_CACHE_HOME, else ~/.cache", () => {
  const yml = resources(appUpdateYml)
  assert.equal(
    updaterPendingFolder(yml, { platform: "linux", env: { XDG_CACHE_HOME: "/xdg" }, home: "/home/a" }),
    join("/xdg", NAME, "pending")
  )
  assert.equal(
    updaterPendingFolder(yml, { platform: "linux", env: {}, home: "/home/a" }),
    join("/home/a", ".cache", NAME, "pending")
  )
})

test("a quoted name is read like a bare one", () => {
  const found = updaterPendingFolder(
    resources(`provider: github\nupdaterCacheDirName: '${NAME}'\n`),
    { platform: "linux", env: {}, home: "/home/a" }
  )
  assert.equal(found, join("/home/a", ".cache", NAME, "pending"))
})

test("no folder when the build names none, or names one outside the cache", () => {
  const where = { platform: "linux" as const, env: {}, home: "/home/a" }
  assert.equal(updaterPendingFolder(resources(null), where), null)
  assert.equal(updaterPendingFolder(resources("provider: github\n"), where), null)
  assert.equal(updaterPendingFolder(resources("updaterCacheDirName: ..\n"), where), null)
  assert.equal(updaterPendingFolder(resources("updaterCacheDirName: a/../..\n"), where), null)
  assert.equal(updaterPendingFolder(resources("updaterCacheDirName: \n"), where), null)
})
