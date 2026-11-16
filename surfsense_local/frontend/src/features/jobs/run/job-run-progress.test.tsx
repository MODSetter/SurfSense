import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { JobRunRead } from "../api"
import { renderJobsDialog } from "../render-jobs-dialog"
import {
  dialogRoutes,
  runRead,
  runSummary,
  stubJobsApi,
  type Answer,
  type StubRequest,
} from "../stub-jobs-api"

import { RUN_POLL_MS } from "./use-job-run"

const GOING: Partial<JobRunRead> = {
  status: "processing",
  progress: null,
  tally: null,
  report: null,
  open_suggestions: [],
  open_suggestion_count: 0,
  newest_ready_version_id: null,
  running: true,
}

/** How each way a run can end reads, as a run the route answers. */
const ENDED = {
  ready: { title: "Done", run: () => runRead() },
  failed: {
    title: "The run stopped",
    run: () => runRead({ ...GOING, status: "failed", running: false }),
  },
  cancelled: {
    title: "Cancelled",
    run: () => runRead({ ...GOING, status: "cancelled", running: false }),
  },
} as const

const ENDINGS = Object.keys(ENDED) as (keyof typeof ENDED)[]

const posts = (calls: StubRequest[], path: string) =>
  calls.filter((call) => call.method === "POST" && call.path === path)

const reads = (calls: StubRequest[], path: string) =>
  calls.filter((call) => call.method === "GET" && call.path === path).length

/** The run as the route answers it now; a test changes it between polls. */
function stubRun(first: JobRunRead, routes: Record<string, Answer> = {}) {
  let current: JobRunRead | null = first
  const calls = stubJobsApi({
    ...dialogRoutes({ runs: [runSummary()] }),
    "GET /workspaces/1/job-runs/41": () =>
      current
        ? Response.json(current)
        : Response.json(
            { detail: { code: "NOT_FOUND", message: "No such job run." } },
            { status: 404 }
          ),
    ...routes,
  })
  return {
    calls,
    set: (next: JobRunRead | null) => {
      current = next
    },
  }
}

function setup() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
}

async function openRun(user: ReturnType<typeof setup>) {
  const rendered = renderJobsDialog()
  await user.click(
    await screen.findByRole("button", {
      name: /^Vendor questionnaire \(revised\)/,
    })
  )
  return rendered
}

const poll = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS)
  })

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("job run progress", () => {
  it("counts the questions answered while the run goes on", async () => {
    const run = stubRun(runRead({ ...GOING, status: "pending" }))
    const user = setup()
    await openRun(user)

    expect(await screen.findByText("Waiting to start…")).toBeTruthy()
    run.set(runRead(GOING))
    await poll()
    expect(await screen.findByText("Reading the workbook…")).toBeTruthy()
    run.set(runRead({ ...GOING, progress: { done: 0, total: 40 } }))
    await poll()
    // Minutes go to reading the documents before the first answer.
    expect(
      await screen.findByText("Reading your documents, then 40 questions…")
    ).toBeTruthy()
    run.set(runRead({ ...GOING, progress: { done: 12, total: 40 } }))
    await poll()
    expect(await screen.findByText("12 of 40 questions")).toBeTruthy()
    expect(
      screen
        .getByRole("progressbar", { name: "Questions answered" })
        .getAttribute("aria-valuenow")
    ).toBe("30")
    run.set(runRead({ ...GOING, progress: { done: 40, total: 40 } }))
    await poll()
    expect(
      await screen.findByText(
        "Writing the answers into a copy of your workbook…"
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "You can close Jobs and keep working. Keep SurfSense open until the run is done: quitting stops it."
      )
    ).toBeTruthy()
  })

  it.each(ENDINGS)(
    "says that a run it saw going has ended, once it is %s",
    async (ending) => {
      const run = stubRun(
        runRead({ ...GOING, progress: { done: 12, total: 40 } })
      )
      const user = setup()
      await openRun(user)
      expect(await screen.findByText("12 of 40 questions")).toBeTruthy()
      const regions = screen.getAllByRole("status")

      run.set(ENDED[ending].run())
      await poll()

      expect(
        await screen.findByRole("heading", { name: ENDED[ending].title })
      ).toBeTruthy()
      const saying = screen
        .getAllByRole("status")
        .filter((region) => region.textContent === ENDED[ending].title)
      expect(saying).toHaveLength(1)
      // A region already on screen while the run went on, so a screen reader says it.
      expect(regions).toContain(saying[0])
    }
  )

  it("announces nothing for a run that had ended before it was opened", async () => {
    stubRun(runRead())
    const user = setup()
    await openRun(user)

    expect(await screen.findByRole("heading", { name: "Done" })).toBeTruthy()
    expect(
      screen
        .queryAllByRole("status")
        .some((region) => region.textContent === "Done")
    ).toBe(false)
  })

  it.each(ENDINGS)(
    "stops reading a run again once it is %s",
    async (ending) => {
      const run = stubRun(
        runRead({ ...GOING, progress: { done: 12, total: 40 } })
      )
      const user = setup()
      await openRun(user)
      expect(await screen.findByText("12 of 40 questions")).toBeTruthy()
      run.set(ENDED[ending].run())
      await poll()
      await screen.findByRole("heading", { name: ENDED[ending].title })
      const read = reads(run.calls, "/workspaces/1/job-runs/41")

      await poll()
      await poll()
      await poll()

      expect(reads(run.calls, "/workspaces/1/job-runs/41")).toBe(read)
    }
  )

  it("stops reading a run again once its view is left", async () => {
    const run = stubRun(
      runRead({ ...GOING, progress: { done: 12, total: 40 } })
    )
    const user = setup()
    await openRun(user)
    expect(await screen.findByText("12 of 40 questions")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "All jobs" }))
    await screen.findByRole("button", { name: "Run Security questionnaire" })
    const read = reads(run.calls, "/workspaces/1/job-runs/41")
    await poll()
    await poll()
    await poll()

    expect(reads(run.calls, "/workspaces/1/job-runs/41")).toBe(read)
  })

  it("cancels a running run", async () => {
    const run = stubRun(
      runRead({ ...GOING, progress: { done: 3, total: 40 } }),
      {
        "POST /artifacts/41/cancel": {},
      }
    )
    const user = setup()
    await openRun(user)
    await waitFor(() =>
      expect(reads(run.calls, "/workspaces/1/artifacts")).toBe(1)
    )

    await user.click(await screen.findByRole("button", { name: "Cancel run" }))

    await waitFor(() =>
      expect(posts(run.calls, "/artifacts/41/cancel")).toHaveLength(1)
    )
    await waitFor(() =>
      expect(reads(run.calls, "/workspaces/1/artifacts")).toBe(2)
    )
  })

  it("says what a finished run holds, and opens its newest ready version in Studio", async () => {
    stubRun(
      runRead({
        newest_version_id: 44,
        newest_version_number: 2,
        newest_ready_version_id: 44,
        report: {
          ...runRead().report!,
          checker: "m",
        },
      })
    )
    const user = setup()
    const { props, openArtifact } = await openRun(user)

    expect(await screen.findByRole("heading", { name: "Done" })).toBeTruthy()
    expect(
      await screen.findByText(
        "SurfSense answered 31 questions of 40 with Qwen3 4B."
      )
    ).toBeTruthy()
    expect(screen.getByText("Each answer was checked again by m.")).toBeTruthy()
    expect(
      within(screen.getByRole("list", { name: "Answers by kind" }))
        .getAllByRole("listitem")
        .map((item) => item.textContent)
    ).toEqual(["Yes 20", "No 8", "N/A 3"])
    expect(
      screen.getByText(
        "6 questions need a person: see the sheet “SurfSense exceptions”."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "2 suggested answers are waiting for you to check and confirm."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "2 rows were left as they were: hidden, locked or already answered."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "Before you send the copy, check the sheets “SurfSense answers” and “SurfSense exceptions”, and delete them if the recipient shouldn’t see them."
      )
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Open in Studio" }))

    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(openArtifact).toHaveBeenCalledWith(44)
  })

  it("confirms a finished run’s suggested answers after asking", async () => {
    const run = stubRun(runRead(), {
      "POST /workspaces/1/job-runs/41/confirm": () =>
        Response.json({ artifact_id: 45 }, { status: 202 }),
    })
    const user = setup()
    await openRun(user)

    await user.click(
      await screen.findByRole("button", { name: "Confirm 2 suggested answers" })
    )
    const question = await screen.findByRole("alertdialog", {
      name: "Confirm 2 suggested answers?",
    })
    expect(
      within(question)
        .getAllByRole("listitem")
        .map((item) => item.textContent)
    ).toEqual([
      "Do you encrypt backups?Suggested: YesQuestions, cell B2",
      "Is there a named security officer?Suggested: Not applicableQuestions, cell B7",
    ])
    expect(posts(run.calls, "/workspaces/1/job-runs/41/confirm")).toHaveLength(
      0
    )
    await user.click(within(question).getByRole("button", { name: "Confirm" }))

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
    const [sent] = posts(run.calls, "/workspaces/1/job-runs/41/confirm")
    expect(sent.body).toBe("{}")
  })

  it("holds the confirmation while a version of the copy is being made", async () => {
    stubRun(runRead({ running: true, newest_version_id: 45 }))
    const user = setup()
    await openRun(user)

    expect(
      (
        (await screen.findByRole("button", {
          name: "Confirm 2 suggested answers",
        })) as HTMLButtonElement
      ).disabled
    ).toBe(true)
  })

  it("says a run stopped, and runs it again or chooses another workbook", async () => {
    const run = stubRun(
      runRead({
        ...GOING,
        status: "failed",
        running: false,
        error:
          "SurfSense found no questions in this workbook. It needs a column of questions and a column for answers, or answer dropdowns.",
      }),
      { "POST /artifacts/41/regenerate": {} }
    )
    const user = setup()
    await openRun(user)

    expect(
      await screen.findByRole("heading", { name: "The run stopped" })
    ).toBeTruthy()
    expect(
      screen.getByText("It didn’t finish, so no answers were written.")
    ).toBeTruthy()
    expect(
      screen.getByText(/^SurfSense found no questions in this workbook\./)
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Run again" }))
    await waitFor(() =>
      expect(posts(run.calls, "/artifacts/41/regenerate")).toHaveLength(1)
    )
    await user.click(
      screen.getByRole("button", { name: "Choose another workbook" })
    )

    expect(
      await screen.findByRole("heading", { name: "Run Security questionnaire" })
    ).toBeTruthy()
  })

  it("says a cancelled run wrote nothing, and runs it again", async () => {
    const run = stubRun(
      runRead({ ...GOING, status: "cancelled", running: false }),
      { "POST /artifacts/41/regenerate": {} }
    )
    const user = setup()
    await openRun(user)

    expect(
      await screen.findByRole("heading", { name: "Cancelled" })
    ).toBeTruthy()
    expect(
      screen.getByText(
        "Nothing was written. Running it again starts from the first question."
      )
    ).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Choose another workbook" })
    ).toBeNull()
    await user.click(screen.getByRole("button", { name: "Run again" }))

    await waitFor(() =>
      expect(posts(run.calls, "/artifacts/41/regenerate")).toHaveLength(1)
    )
  })

  it("shows why a run could not be run again", async () => {
    stubRun(runRead({ ...GOING, status: "cancelled", running: false }), {
      "POST /artifacts/41/regenerate": () =>
        Response.json(
          { detail: { code: "sources_gone", message: "The backend’s own." } },
          { status: 409 }
        ),
    })
    const user = setup()
    await openRun(user)

    await user.click(await screen.findByRole("button", { name: "Run again" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "None of this artifact’s sources are left."
    )
  })

  it("says a deleted run is gone", async () => {
    const run = stubRun(runRead())
    run.set(null)
    const user = setup()
    await openRun(user)

    expect(await screen.findByText("This run was deleted.")).toBeTruthy()
  })
})
