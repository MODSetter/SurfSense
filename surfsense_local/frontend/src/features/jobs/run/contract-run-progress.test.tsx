import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { renderJobsDialog } from "../render-jobs-dialog"
import {
  TEST_PACK,
  TEST_REDLINE_PACK,
  dialogRoutes,
  redlineRunRead,
  redlineRunSummary,
  stubJobsApi,
} from "../stub-jobs-api"

const PACKS = [TEST_PACK, TEST_REDLINE_PACK]

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function openRedline(read = redlineRunRead()) {
  stubJobsApi({
    ...dialogRoutes({ packs: PACKS, runs: [redlineRunSummary()] }),
    "GET /workspaces/1/job-runs/51": read,
  })
  const user = userEvent.setup()
  renderJobsDialog()
  await user.click(
    await screen.findByRole("button", { name: /^Acme NDA \(revised\)/ })
  )
}

describe("a contract redline's run", () => {
  it("lists a finished redline by its review points", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS, runs: [redlineRunSummary()] }))
    renderJobsDialog()

    const listed = await screen.findByRole("button", {
      name: /^Acme NDA \(revised\)/,
    })
    expect(within(listed).getByText("Done, 17 review points")).toBeTruthy()
  })

  it("says what each review point came to and which a person must take over", async () => {
    await openRedline()

    expect(
      await screen.findByText(
        /^SurfSense checked 17 review points against your playbook with /
      )
    ).toBeTruthy()
    const outcomes = screen.getByRole("list", {
      name: "Review points by outcome",
    })
    expect(
      within(outcomes)
        .getAllByRole("listitem")
        .map((item) => item.textContent)
    ).toEqual([
      "5 changed",
      "8 meet your playbook",
      "2 not in your playbook",
      "2 for a person",
    ])
    expect(
      screen.getByText(
        "2 review points need a person. Each has an internal comment in Studio that says why."
      )
    ).toBeTruthy()
    expect(screen.getByText("Survival, at P9 (4.2)")).toBeTruthy()
    expect(screen.getByText("Return or destruction")).toBeTruthy()
    // A workbook's wording never shows for a contract.
    expect(screen.queryByText(/sheet/)).toBeNull()
  })

  it("counts review points while it runs", async () => {
    await openRedline(
      redlineRunRead({
        status: "processing",
        progress: { done: 3, total: 17 },
        tally: null,
        report: null,
        running: true,
      })
    )

    expect(await screen.findByText("3 of 17 review points")).toBeTruthy()
    expect(
      screen.getByRole("progressbar", { name: "Review points checked" })
    ).toBeTruthy()
  })

  it("says a failed redline changed nothing and offers another contract", async () => {
    await openRedline(
      redlineRunRead({
        status: "failed",
        report: null,
        tally: null,
        running: false,
      })
    )

    expect(
      await screen.findByText("It didn’t finish, so nothing was changed.")
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Choose another contract" })
    ).toBeTruthy()
  })
})
