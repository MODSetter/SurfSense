import assert from "node:assert/strict"
import test from "node:test"

import { APT_SOURCE, installChannel } from "./install-channel.ts"

const RESOURCES = "/opt/SurfSense/resources"
const OWN_SNAP = { SNAP: "/snap/surfsense-local/12", SNAP_NAME: "surfsense-local" }
const SNAP_EXEC = "/snap/surfsense-local/12/app/surfsense-local"

function missing(): never {
  throw Object.assign(new Error("ENOENT"), { code: "ENOENT" })
}

/** A Linux install with these files on disk and this environment. */
function linux(options: {
  files?: Record<string, string>
  env?: Record<string, string>
  execPath?: string
  paths?: string[]
}) {
  const files = options.files ?? {}
  const paths = new Set([...(options.paths ?? []), ...Object.keys(files)])
  return installChannel({
    platform: "linux",
    env: options.env ?? {},
    execPath: options.execPath ?? "/opt/SurfSense/surfsense-local",
    resourcesPath: RESOURCES,
    readFile: (path) => (path in files ? files[path]! : missing()),
    exists: (path) => paths.has(path),
  })
}

test("a packager's marker names the channel that owns updates", () => {
  for (const id of ["scoop", "aur", "snap", "flatpak", "nix", "apt"] as const) {
    assert.equal(linux({ files: { [`${RESOURCES}/install-channel`]: `${id}\n` } }), id)
  }
  const scoop = installChannel({
    platform: "win32",
    env: {},
    execPath: "C:\\Users\\ada\\scoop\\apps\\surfsense\\current\\SurfSense.exe",
    resourcesPath: "C:\\Users\\ada\\scoop\\apps\\surfsense\\current\\resources",
    readFile: (path) =>
      path === "C:\\Users\\ada\\scoop\\apps\\surfsense\\current\\resources\\install-channel"
        ? "scoop"
        : missing(),
    exists: () => false,
  })
  assert.equal(scoop, "scoop")
})

test("an empty or unknown marker is ignored", () => {
  for (const junk of ["", "  \n", "brew", "AUR", "snap store"]) {
    assert.equal(linux({ files: { [`${RESOURCES}/install-channel`]: junk } }), null, junk)
  }
})

test("a snap is known from snapd's environment and an app inside $SNAP", () => {
  assert.equal(linux({ env: OWN_SNAP, execPath: SNAP_EXEC }), "snap")
  // Half of it is not a snap.
  assert.equal(linux({ env: { SNAP: OWN_SNAP.SNAP }, execPath: SNAP_EXEC }), null)
  assert.equal(linux({ env: { SNAP_NAME: OWN_SNAP.SNAP_NAME }, execPath: SNAP_EXEC }), null)
})

test("another snap's variables, inherited by a normal install, are not SurfSense's snap", () => {
  const deb = { [`${RESOURCES}/package-type`]: "deb\n" }
  const others = [
    { SNAP: "/snap/nvim/123", SNAP_NAME: "nvim" },
    { SNAP: "/snap/pycharm-community/456", SNAP_NAME: "pycharm-community" },
    // SurfSense's own snap's shell, running the deb.
    OWN_SNAP,
  ]
  for (const env of others) {
    assert.equal(linux({ env }), null, env.SNAP_NAME)
    assert.equal(linux({ env, files: deb, paths: [APT_SOURCE] }), "apt", env.SNAP_NAME)
  }
})

test("a flatpak is known from FLATPAK_ID or /.flatpak-info", () => {
  assert.equal(linux({ env: { FLATPAK_ID: "com.surfsense.app" } }), "flatpak")
  assert.equal(linux({ paths: ["/.flatpak-info"] }), "flatpak")
})

test("an app run from the Nix store is a Nix install", () => {
  assert.equal(
    linux({ execPath: "/nix/store/0c9x2k-surfsense-2.2.4/opt/SurfSense/surfsense-local" }),
    "nix"
  )
})

test("a deb belongs to apt only once SurfSense's apt source is configured", () => {
  const deb = { [`${RESOURCES}/package-type`]: "deb\n" }

  assert.equal(linux({ files: deb, paths: [APT_SOURCE] }), "apt")
  // The same deb installed by hand updates itself.
  assert.equal(linux({ files: deb }), null)
  // An rpm or AppImage beside a stray apt source is not apt's.
  assert.equal(linux({ files: { [`${RESOURCES}/package-type`]: "rpm" }, paths: [APT_SOURCE] }), null)
  assert.equal(linux({ paths: [APT_SOURCE] }), null)
})

test("a marker wins over what the environment suggests", () => {
  const aurInSnapEnv = linux({
    files: { [`${RESOURCES}/install-channel`]: "aur" },
    env: OWN_SNAP,
    execPath: SNAP_EXEC,
  })
  assert.equal(aurInSnapEnv, "aur")
})

test("Linux-only signs mean nothing on Windows or macOS", () => {
  const signs = [
    { env: OWN_SNAP, execPath: SNAP_EXEC },
    { env: { FLATPAK_ID: "com.surfsense.app" }, execPath: "/opt/SurfSense/surfsense-local" },
    { env: {}, execPath: "/nix/store/abc/SurfSense" },
  ]
  for (const platform of ["win32", "darwin"]) {
    for (const { env, execPath } of signs) {
      const channel = installChannel({
        platform,
        env,
        execPath,
        resourcesPath: RESOURCES,
        readFile: missing,
        exists: () => true,
      })
      assert.equal(channel, null, `${platform} ${execPath}`)
    }
  }
})

test("an install it cannot read is a plain install, never a crash", () => {
  const unreadable = installChannel({
    platform: "linux",
    env: {},
    execPath: "/opt/SurfSense/surfsense-local",
    resourcesPath: RESOURCES,
    readFile: () => {
      throw Object.assign(new Error("EACCES"), { code: "EACCES" })
    },
    exists: () => {
      throw new Error("EACCES")
    },
  })
  assert.equal(unreadable, null)
  assert.equal(linux({}), null)
})
