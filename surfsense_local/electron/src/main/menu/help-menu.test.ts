import assert from "node:assert/strict"
import test from "node:test"

import type { MenuItemConstructorOptions } from "electron"

import { allowedExternalUrl } from "../external-url.ts"
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
  // Only surfsense.com's link says where the visit came from.
  assert.deepEqual(opened, [
    "https://www.surfsense.com/docs?utm_source=desktop&utm_medium=app&utm_content=help_menu&app_version=2.0.2",
    "https://github.com/MODSetter/SurfSense",
    "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2",
  ])
})

test("every link it opens passes the external-link allowlist unchanged", () => {
  const { click, opened } = setup()
  click("Documentation")
  click("Source Code on GitHub")
  click("Release Notes")
  for (const url of opened) assert.equal(allowedExternalUrl(url), url)
})
