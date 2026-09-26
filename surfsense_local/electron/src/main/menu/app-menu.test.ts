import assert from "node:assert/strict"
import test from "node:test"

import type { MenuItemConstructorOptions } from "electron"

import { appMenu } from "./app-menu.ts"

test("offers Check for Updates… right under About", () => {
  let checks = 0
  const menu = appMenu({ checkForUpdates: () => (checks += 1) })
  const items = menu.submenu as MenuItemConstructorOptions[]

  assert.equal(menu.role, "appMenu")
  assert.equal(items[0].role, "about")
  assert.equal(items[1].label, "Check for Updates…")
  ;(items[1].click as () => void)()
  assert.equal(checks, 1)
})

test("keeps the rest of the standard macOS app menu", () => {
  const items = appMenu({ checkForUpdates: () => {} })
    .submenu as MenuItemConstructorOptions[]
  const roles = items.map((item) => item.role).filter(Boolean)
  assert.deepEqual(roles, [
    "about",
    "services",
    "hide",
    "hideOthers",
    "unhide",
    "quit",
  ])
})
