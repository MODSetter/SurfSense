import assert from "node:assert/strict"
import { join } from "node:path"
import test from "node:test"

import { dataDirs } from "./data-dir.ts"

const SNAP_ENV = {
  SNAP: "/snap/surfsense-local/12",
  SNAP_NAME: "surfsense-local",
  SNAP_USER_COMMON: "/home/ada/snap/surfsense-local/common",
}
const SNAP_EXEC = "/snap/surfsense-local/12/app/surfsense-local"
const DEB_EXEC = "/opt/SurfSense/surfsense-local"

test("an install keeps its data in ~/.surfsense, and dev in ~/.surfsense-dev", () => {
  assert.deepEqual(dataDirs({ packaged: true, env: {}, home: "/home/ada", execPath: DEB_EXEC }), {
    data: join("/home/ada", ".surfsense"),
    temp: null,
  })
  assert.deepEqual(dataDirs({ packaged: false, env: {}, home: "/home/ada", execPath: DEB_EXEC }), {
    data: join("/home/ada", ".surfsense-dev"),
    temp: null,
  })
})

test("a snap keeps its data and temp files in SNAP_USER_COMMON, which survives a refresh", () => {
  // HOME is the per-revision SNAP_USER_DATA there.
  const dirs = dataDirs({
    packaged: true,
    env: SNAP_ENV,
    home: "/home/ada/snap/surfsense-local/12",
    execPath: SNAP_EXEC,
  })

  assert.deepEqual(dirs, {
    data: "/home/ada/snap/surfsense-local/common/.surfsense",
    temp: "/home/ada/snap/surfsense-local/common/tmp",
  })
})

test("dev ignores a snap's environment, and half of one is not a snap", () => {
  assert.deepEqual(dataDirs({ packaged: false, env: SNAP_ENV, home: "/home/ada", execPath: SNAP_EXEC }), {
    data: join("/home/ada", ".surfsense-dev"),
    temp: null,
  })
  const { SNAP_USER_COMMON, ...noCommon } = SNAP_ENV
  for (const env of [{ SNAP: SNAP_ENV.SNAP }, { SNAP_USER_COMMON }, noCommon]) {
    assert.deepEqual(dataDirs({ packaged: true, env, home: "/home/ada", execPath: SNAP_EXEC }), {
      data: join("/home/ada", ".surfsense"),
      temp: null,
    })
  }
})

test("another snap's variables, inherited by a normal install, leave its data in ~/.surfsense", () => {
  const others = [
    { SNAP: "/snap/nvim/123", SNAP_NAME: "nvim", SNAP_USER_COMMON: "/home/ada/snap/nvim/common" },
    {
      SNAP: "/snap/pycharm-community/456",
      SNAP_NAME: "pycharm-community",
      SNAP_USER_COMMON: "/home/ada/snap/pycharm-community/common",
    },
    // SurfSense's own snap's shell, running the deb.
    SNAP_ENV,
  ]
  for (const env of others) {
    const dirs = dataDirs({ packaged: true, env, home: "/home/ada", execPath: DEB_EXEC })
    assert.deepEqual(dirs, { data: join("/home/ada", ".surfsense"), temp: null }, env.SNAP_NAME)
  }
})
