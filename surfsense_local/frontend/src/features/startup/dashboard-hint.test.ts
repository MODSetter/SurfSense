import { afterEach, describe, expect, it } from "vitest"

import {
  expectsDashboard,
  forgetDashboard,
  rememberDashboard,
} from "./dashboard-hint"

function onDatabase(identity: string | null) {
  window.surfsense = {
    databaseIdentity: () => identity,
  } as unknown as Window["surfsense"]
}

afterEach(() => {
  window.surfsense = undefined
  localStorage.clear()
})

describe("dashboard hint", () => {
  it("expects nothing before onboarding has been seen done", () => {
    onDatabase("a")
    expect(expectsDashboard()).toBe(false)
  })

  it("expects the dashboard on the database it was remembered for", () => {
    onDatabase("a")
    rememberDashboard()
    expect(expectsDashboard()).toBe(true)
  })

  it("expects nothing once the database has been made again", () => {
    onDatabase("a")
    rememberDashboard()
    onDatabase("b")
    expect(expectsDashboard()).toBe(false)
  })

  it("expects nothing once onboarding is required again", () => {
    onDatabase("a")
    rememberDashboard()
    forgetDashboard()
    expect(expectsDashboard()).toBe(false)
  })

  it("expects nothing while the database does not exist yet", () => {
    onDatabase(null)
    rememberDashboard()
    expect(expectsDashboard()).toBe(false)
  })

  it("expects nothing without the desktop's database identity", () => {
    rememberDashboard()
    expect(expectsDashboard()).toBe(false)
  })
})
