import assert from "node:assert/strict"
import test from "node:test"

import type { MenuItemConstructorOptions } from "electron"

import { helpMenu } from "./help-menu.ts"

function setup() {
  const opened: string[] = []
  let reported = 0
  const menu = helpMenu({
    version: "2.0.2",
    openExternal: (url) => opened.push(url),
    reportIssue: () => (reported += 1),
  })
  const click = (label: string) => {
    const items = menu.submenu as MenuItemConstructorOptions[]
    const item = items.find((entry) => entry.label === label)
    assert.ok(item?.click, `no ${label} item`)
    ;(item.click as () => void)()
  }
  return { menu, opened, reported: () => reported, click }
}

test("is the OS's Help menu", () => {
  assert.equal(setup().menu.role, "help")
})

test("Report Issue… opens the in-app report", () => {
  const { click, opened, reported } = setup()
  click("Report Issue…")
  assert.equal(reported(), 1)
  assert.deepEqual(opened, [])
})

test("links to the docs, the source and this version's release notes", () => {
  const { click, opened } = setup()
  click("Documentation")
  click("Source Code on GitHub")
  click("Release Notes")
  assert.deepEqual(opened, [
    "https://www.surfsense.com/docs",
    "https://github.com/MODSetter/SurfSense",
    "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2",
  ])
})
