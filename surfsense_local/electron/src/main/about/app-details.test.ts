import assert from "node:assert/strict"
import test from "node:test"

import { appDetails } from "./app-details.ts"

test("describes the build and the OS it runs on", () => {
  assert.deepEqual(
    appDetails({
      version: "2.0.2",
      versions: { electron: "44.0.0", chrome: "146.0.1", node: "24.1.0" },
      platform: "darwin",
      systemVersion: "15.4",
      arch: "arm64",
    }),
    {
      version: "2.0.2",
      electron: "44.0.0",
      chrome: "146.0.1",
      node: "24.1.0",
      os: "macOS 15.4",
      arch: "arm64",
    }
  )
})

test("names Windows and Linux, and passes an unknown platform through", () => {
  const base = {
    version: "2.0.2",
    versions: { electron: "44.0.0", chrome: "146.0.1", node: "24.1.0" },
    arch: "x64",
  }
  assert.equal(
    appDetails({ ...base, platform: "win32", systemVersion: "10.0.26100" }).os,
    "Windows 10.0.26100"
  )
  assert.equal(
    appDetails({ ...base, platform: "linux", systemVersion: "6.8.0" }).os,
    "Linux 6.8.0"
  )
  assert.equal(
    appDetails({ ...base, platform: "freebsd", systemVersion: "14.1" }).os,
    "freebsd 14.1"
  )
})
