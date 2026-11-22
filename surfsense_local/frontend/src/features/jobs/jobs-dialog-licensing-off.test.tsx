import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"

import { renderJobsDialog } from "./render-jobs-dialog"
import {
  BUSINESS,
  NO_LICENSE,
  dialogRoutes,
  lockedPack,
  stubJobsApi,
} from "./stub-jobs-api"

// As every release runs since SurfSense became free (ADR 0092).
const FREE = { ...NO_LICENSE, licensing: false }

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("jobs dialog with licensing off", () => {
  it("runs every installed job, with no license and nothing to buy", async () => {
    // Locked as a licensing build would say: the dialog no longer asks.
    stubJobsApi(dialogRoutes({ license: FREE, packs: [lockedPack("none")] }))
    renderJobsDialog()

    const name = await screen.findByRole("heading", {
      name: "Security questionnaire",
    })
    const row = within(name.closest("li")!)
    expect(
      row.getByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(row.queryByText("Business")).toBeNull()
    expect(row.queryByText("Locked")).toBeNull()
    expect(screen.queryByRole("region", { name: "License" })).toBeNull()
    expect(
      screen.queryByRole("link", { name: "Start 14-day trial" })
    ).toBeNull()
    expect(screen.queryByRole("link", { name: "See pricing" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Add license" })).toBeNull()
  })

  it("lists only what is installed, and imports a pack file instead of downloading", async () => {
    stubJobsApi(dialogRoutes({ license: FREE, packs: [] }))
    renderJobsDialog()

    expect(
      await screen.findByRole("button", { name: "Import pack file" })
    ).toBeTruthy()
    expect(
      screen.queryByRole("heading", { name: "Security questionnaire" })
    ).toBeNull()
    expect(
      screen.queryByRole("heading", { name: "Contract redline" })
    ).toBeNull()
    expect(screen.queryByRole("button", { name: /^Download/ })).toBeNull()
  })

  it("names no licensed firm, even for a license imported earlier", async () => {
    stubJobsApi(dialogRoutes({ license: { ...BUSINESS, licensing: false } }))
    renderJobsDialog()

    await screen.findByRole("heading", { name: "Security questionnaire" })
    expect(screen.queryByText(/Licensed to/)).toBeNull()
  })
})
