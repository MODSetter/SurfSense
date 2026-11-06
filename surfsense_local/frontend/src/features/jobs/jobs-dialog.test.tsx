import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster, toast } from "sonner"

import type { JobRunSummary, PackDownload, PackInfo } from "./api"
import { renderJobsDialog } from "./render-jobs-dialog"
import { RUNS_POLL_MS } from "./runs/use-job-runs"
import {
  BUSINESS,
  BUSINESS_TRIAL,
  INDIVIDUAL,
  LICENSE_SERVER_OFF,
  NO_LICENSE,
  TEST_PACK,
  dialogRoutes,
  lockedPack,
  packOutcome,
  refusal,
  runRead,
  runSummary,
  showWindowAgainLater,
  stubJobsApi,
  stubOpenExternal,
  type StubRequest,
} from "./stub-jobs-api"

const TAGS = "utm_source=desktop&utm_medium=app"

const WAITING =
  "A run of Security questionnaire was under way, so any newer version waits. SurfSense checks again once the run ends."

const WAITING_ON_ITS_PACK =
  "Security questionnaire comes in the same pack as a job whose run was under way, so it waits. SurfSense tries again once the run ends."

function downloaded(
  outcome: PackDownload["outcomes"][number]["outcome"],
  packs = [TEST_PACK]
): PackDownload {
  // The version on this computer once the answer is in, which these carry.
  const kept = ["installed", "current", "deferred"].includes(outcome)
  return {
    outcomes: [packOutcome(outcome, { version: kept ? "0.4.3" : null })],
    packs,
  }
}

/** A response the test lets go of, to see what shows while it is out. */
function held<T>(body: T) {
  let release: () => void = () => undefined
  const answer = () =>
    new Promise<Response>((resolve) => {
      release = () => resolve(Response.json(body))
    })
  return { answer, release: () => release() }
}

const posted = (calls: StubRequest[], path: string) =>
  calls.filter((call) => call.method === "POST" && call.path === path)

const zip = () =>
  new File(["PK"], "test-pack-0.4.3.zip", { type: "application/zip" })

/** The questionnaire's row once the list is read: each job sold has its own. */
async function questionnaireRow() {
  const name = await screen.findByRole("heading", {
    name: "Security questionnaire",
  })
  return name.closest("li")!
}

afterEach(() => {
  // Sonner keeps its toasts across tests; one left over would show in the next Toaster.
  toast.dismiss()
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  delete window.surfsense
})

describe("jobs dialog", () => {
  it("offers the 14-day trial and pricing for a job no license here includes", async () => {
    stubJobsApi(dialogRoutes({ license: NO_LICENSE, packs: [] }))
    const openExternal = stubOpenExternal()
    const user = userEvent.setup()
    renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "Comes with a SurfSense Business license. Try it free for 14 days."
      )
    ).toBeTruthy()
    await user.click(row.getByRole("link", { name: "Start 14-day trial" }))
    await user.click(row.getByRole("link", { name: "See pricing" }))

    expect(openExternal.mock.calls).toEqual([
      [`https://www.surfsense.com/downloads?${TAGS}&utm_content=jobs_trial`],
      [`https://www.surfsense.com/pricing?${TAGS}&utm_content=jobs_pricing`],
    ])
  })

  it("closes Jobs for Settings › License to add the license", async () => {
    stubJobsApi(dialogRoutes({ license: NO_LICENSE, packs: [] }))
    const user = userEvent.setup()
    const { props } = renderJobsDialog()
    const row = within(await questionnaireRow())

    await user.click(row.getByRole("button", { name: "Add license" }))

    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(props.onOpenLicense).toHaveBeenCalledOnce()
  })

  it("tells an Individual license that jobs come with Business, and offers no trial", async () => {
    stubJobsApi(dialogRoutes({ license: INDIVIDUAL, packs: [] }))
    renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "Your Individual license doesn’t include this job: jobs come with Business. If your license has moved to Business, Check for renewal fetches its new file."
      )
    ).toBeTruthy()
    expect(row.getByRole("button", { name: "Check for renewal" })).toBeTruthy()
    expect(row.getByRole("link", { name: "See pricing" })).toBeTruthy()
    expect(
      screen.queryByRole("link", { name: "Start 14-day trial" })
    ).toBeNull()
  })

  it("tells a trial without the job that Business includes it", async () => {
    stubJobsApi(
      dialogRoutes({
        license: { ...BUSINESS_TRIAL, jobs: [] },
        packs: [lockedPack("not_included")],
      })
    )
    renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "Your license doesn’t include this job. It comes with a Business license, which you can try free for 14 days."
      )
    ).toBeTruthy()
    expect(row.getByRole("link", { name: "Start 14-day trial" })).toBeTruthy()
    expect(row.getByRole("button", { name: "Replace license" })).toBeTruthy()
  })

  it("offers Check for renewal and pricing once a Business license has ended", async () => {
    stubJobsApi(
      dialogRoutes({
        license: { ...BUSINESS, state: "license_expired" },
        packs: [lockedPack("expired")],
      })
    )
    renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "Your license has ended, so this job can’t run. If it was renewed, Check for renewal fetches the new file."
      )
    ).toBeTruthy()
    expect(row.getByRole("button", { name: "Check for renewal" })).toBeTruthy()
    expect(row.getByRole("link", { name: "See pricing" })).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Run Security questionnaire" })
    ).toBeNull()
  })

  it("offers pricing and Replace license once a trial has ended, which opens Settings › License", async () => {
    stubJobsApi(
      dialogRoutes({
        license: { ...BUSINESS_TRIAL, state: "license_expired" },
        packs: [lockedPack("expired")],
      })
    )
    const user = userEvent.setup()
    const { props } = renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "Your 14-day trial has ended. To keep running jobs, buy a Business license, then replace the trial’s license with the one we email you."
      )
    ).toBeTruthy()
    expect(row.getByRole("link", { name: "See pricing" })).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Check for renewal" })
    ).toBeNull()
    await user.click(row.getByRole("button", { name: "Replace license" }))

    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(props.onOpenLicense).toHaveBeenCalledOnce()
  })

  it("says the clock is behind instead of offering the job", async () => {
    stubJobsApi(
      dialogRoutes({
        license: { ...BUSINESS, state: "clock_untrusted" },
        packs: [lockedPack("clock")],
      })
    )
    renderJobsDialog()
    const row = within(await questionnaireRow())

    expect(
      row.getByText(
        "This computer’s clock is behind the last time SurfSense ran. Set the clock right to run this job."
      )
    ).toBeTruthy()
    expect(row.queryAllByRole("button")).toHaveLength(0)
  })

  it("names the firm the license is for", async () => {
    stubJobsApi(dialogRoutes())
    renderJobsDialog()

    expect(
      await screen.findByText("Licensed to Example Accounting LLP")
    ).toBeTruthy()
  })

  it("downloads a job the license includes, then offers to run it", async () => {
    const download = held(downloaded("installed"))
    const calls = stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": download.answer,
    })
    const user = userEvent.setup()
    renderJobsDialog({}, { beside: <Toaster /> })

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )
    expect(await screen.findByText("Downloading…")).toBeTruthy()
    download.release()

    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(
      await screen.findByText("Security questionnaire is ready to run")
    ).toBeTruthy()
    expect(screen.getByText("Version 0.4.3")).toBeTruthy()
    expect(screen.queryByText("Downloading…")).toBeNull()
    // No body: the backend asks for every job the stored license includes.
    expect(posted(calls, "/job-packs/download")[0].body).toBeUndefined()
  })

  it("offers support beside Download for a computer without internet", async () => {
    stubJobsApi(dialogRoutes({ packs: [] }))
    const openExternal = stubOpenExternal()
    const user = userEvent.setup()
    renderJobsDialog()

    expect(
      await screen.findByText(
        "No internet on this computer? Ask SurfSense support for the job pack file, then import it."
      )
    ).toBeTruthy()
    await user.click(screen.getByRole("link", { name: "Contact support" }))

    expect(openExternal).toHaveBeenCalledWith(
      `https://www.surfsense.com/contact?${TAGS}&utm_content=jobs_support`
    )
  })

  it("asks about the license server before downloading, and says where to allow it on Cancel", async () => {
    const calls = stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": LICENSE_SERVER_OFF,
    })
    const user = userEvent.setup()
    renderJobsDialog({}, { consent: true })

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )
    const question = await screen.findByRole("alertdialog")
    await user.click(within(question).getByRole("button", { name: "Cancel" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "SurfSense didn’t contact its license server, api.surfsense.com. Try again and choose Allow, or allow it in Settings › Network."
    )
    expect(posted(calls, "/job-packs/download")).toHaveLength(1)
    expect(calls.some((call) => call.path === "/egress")).toBe(false)
  })

  it("says why the license server sent no job", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": downloaded("needs_newer_app", []),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Security questionnaire needs a newer version of SurfSense. Update the app, then download it again."
    )
    // Still offered, to try again once the app is updated.
    expect(
      screen.getByRole("button", { name: "Download Security questionnaire" })
    ).toBeTruthy()
  })

  it("says nothing more when the newest version is already installed", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": downloaded("current"),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
    expect(screen.queryByText(/under way/)).toBeNull()
  })

  it("says any newer version waits while a run of the job is under way", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": downloaded("deferred"),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect((await screen.findByText(WAITING)).getAttribute("role")).toBe(
      "status"
    )
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("stops saying a newer version waits once another version is in place", async () => {
    let listed: PackInfo[] = []
    stubJobsApi({
      ...dialogRoutes(),
      "GET /job-packs": () => Response.json(listed),
      "POST /job-packs/download": downloaded("deferred"),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )
    // The version the check was held back from replacing is still the one here.
    expect(await screen.findByText(WAITING)).toBeTruthy()
    expect(screen.getByText("Version 0.4.3")).toBeTruthy()
    // The check made once the run ended put a newer version in place.
    listed = [{ ...TEST_PACK, version: "0.5.0" }]
    showWindowAgainLater()

    expect(await screen.findByText("Version 0.5.0")).toBeTruthy()
    expect(screen.queryByText(WAITING)).toBeNull()
  })

  it("says a newer version waits while two packs have the job and the newer is kept", async () => {
    // A developer's pack, listed first, has the same job at an older version.
    const devPack: PackInfo = {
      ...TEST_PACK,
      id: "a-dev-pack",
      version: "0.1.0",
    }
    let listed: PackInfo[] = []
    stubJobsApi({
      ...dialogRoutes(),
      "GET /job-packs": () => Response.json(listed),
      // The backend names the newest installed pack with the job.
      "POST /job-packs/download": downloaded("deferred", [devPack, TEST_PACK]),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect(await screen.findByText(WAITING)).toBeTruthy()
    expect(screen.getByText("Version 0.1.0")).toBeTruthy()
    // The check made once the run ended put a newer version of that pack in place.
    listed = [devPack, { ...TEST_PACK, version: "0.5.0" }]
    showWindowAgainLater()

    await waitFor(() => expect(screen.queryByText(WAITING)).toBeNull())
  })

  it("says a job not downloaded yet waits while a run of another job in its pack is under way", async () => {
    let listed: PackInfo[] = []
    stubJobsApi({
      ...dialogRoutes(),
      "GET /job-packs": () => Response.json(listed),
      // No version: no pack here has the job. The backend sends this only
      // when the pack that adds the job waits on a run of another of its jobs.
      "POST /job-packs/download": {
        outcomes: [packOutcome("deferred")],
        packs: [],
      },
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect(
      (await screen.findByText(WAITING_ON_ITS_PACK)).getAttribute("role")
    ).toBe("status")
    expect(screen.queryByText(WAITING)).toBeNull()
    expect(screen.queryByRole("alert")).toBeNull()
    expect(
      screen.getByRole("button", { name: "Download Security questionnaire" })
    ).toBeTruthy()
    // The download made once the run ended put the job in place.
    listed = [TEST_PACK]
    showWindowAgainLater()

    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(screen.queryByText(WAITING_ON_ITS_PACK)).toBeNull()
  })

  it.each([
    [
      "the job comes only in a pack with a job the license lacks",
      packOutcome("pack_not_covered", { detail: "pack_not_covered" }),
      "Security questionnaire comes only in a pack with a job your license doesn’t include, so SurfSense’s license server sent nothing. Contact SurfSense support.",
    ],
    [
      "the pack sent holds a job this computer’s license file lacks",
      packOutcome("license_outdated", { detail: "PACK_NOT_INCLUDED" }),
      "Your license has changed on SurfSense’s license server. Check for renewal in Settings › License, then download Security questionnaire again.",
    ],
  ])("says what to do on the row when %s", async (_, outcome, said) => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": { outcomes: [outcome], packs: [] },
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )

    expect((await screen.findByRole("alert")).textContent).toBe(said)
    // The row still says the license includes the job, and offers it again.
    expect(
      screen.getByText(
        "Your license includes this job. Download it to run it on this computer."
      )
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Download Security questionnaire" })
    ).toBeTruthy()
  })

  it("imports a pack file the user picks", async () => {
    const calls = stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/import": [TEST_PACK],
    })
    const user = userEvent.setup()
    renderJobsDialog({}, { beside: <Toaster /> })
    const file = zip()

    await user.upload(
      await screen.findByLabelText("Choose a job pack file"),
      file
    )

    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(
      await screen.findByText(
        "Security questionnaire version 0.4.3 is installed"
      )
    ).toBeTruthy()
    const [sent] = posted(calls, "/job-packs/import")
    expect(sent.body).toBeInstanceOf(FormData)
    expect((sent.body as FormData).get("file")).toBe(file)
  })

  it("forgets what the download came to once the job’s pack file is imported", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/download": downloaded("unavailable", []),
      "POST /job-packs/import": [TEST_PACK],
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: "Download Security questionnaire",
      })
    )
    expect((await screen.findByRole("alert")).textContent).toBe(
      "SurfSense’s license server couldn’t send Security questionnaire. Try again later."
    )
    // What the row says to do on a computer without internet.
    await user.upload(screen.getByLabelText("Choose a job pack file"), zip())

    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("explains a pack file it refused", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: [] }),
      "POST /job-packs/import": refusal(422, "PACK_BAD_SIGNATURE"),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.upload(
      await screen.findByLabelText("Choose a job pack file"),
      zip()
    )

    expect((await screen.findByRole("alert")).textContent).toBe(
      "This job pack was changed after SurfSense signed it, or SurfSense didn’t sign it, so it can’t be used."
    )
  })

  it("refuses a file larger than a pack before sending it", async () => {
    const calls = stubJobsApi(dialogRoutes({ packs: [] }))
    const user = userEvent.setup()
    renderJobsDialog()
    const large = zip()
    Object.defineProperty(large, "size", { value: 50 * 1024 * 1024 + 1 })

    await user.upload(
      await screen.findByLabelText("Choose a job pack file"),
      large
    )

    expect((await screen.findByRole("alert")).textContent).toBe(
      "This file is larger than a job pack can be (50 MB)."
    )
    expect(posted(calls, "/job-packs/import")).toHaveLength(0)
  })

  it("lists recent runs newest first, with how far each has got", async () => {
    stubJobsApi(
      dialogRoutes({
        runs: [
          runSummary({
            artifact_id: 44,
            title: "Due diligence (revised)",
            status: "pending",
            progress: null,
            tally: null,
            open_suggestion_count: 0,
            running: true,
          }),
          runSummary({
            artifact_id: 43,
            title: "Insurer form (revised)",
            status: "processing",
            progress: { done: 12, total: 40 },
            tally: null,
            open_suggestion_count: 0,
            running: true,
          }),
          runSummary(),
        ],
      })
    )
    renderJobsDialog()

    await screen.findByText("Due diligence (revised)")
    const runs = screen.getByRole("heading", { name: "Recent runs" })
    const items = within(runs.parentElement!).getAllByRole("listitem")
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringMatching(
        /^Due diligence \(revised\)Security questionnaire, .*Waiting to start$/
      ),
      expect.stringMatching(
        /^Insurer form \(revised\)Security questionnaire, .*12 of 40 questions$/
      ),
      expect.stringMatching(
        /^Vendor questionnaire \(revised\)Security questionnaire, .*Done, 40 questions2 suggestions to confirm$/
      ),
    ])
    expect(screen.queryByText("Older runs are in Studio.")).toBeNull()
  })

  it("reads recent runs again while one goes on, and stops once none does", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let runs: JobRunSummary[] = [
      runSummary({
        status: "processing",
        progress: { done: 12, total: 40 },
        tally: null,
        open_suggestion_count: 0,
        running: true,
      }),
    ]
    const calls = stubJobsApi({
      ...dialogRoutes(),
      "GET /workspaces/1/job-runs?limit=11": () => Response.json(runs),
    })
    const reads = () =>
      calls.filter((call) => call.path === "/workspaces/1/job-runs?limit=11")
        .length
    const wait = (ms: number) =>
      act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
      })
    renderJobsDialog()

    expect(await screen.findByText("12 of 40 questions")).toBeTruthy()
    expect(reads()).toBe(1)
    runs = [runSummary()]
    await wait(RUNS_POLL_MS)
    expect(await screen.findByText("Done, 40 questions")).toBeTruthy()
    expect(reads()).toBe(2)
    await wait(RUNS_POLL_MS * 3)

    expect(reads()).toBe(2)
  })

  it("says older runs are in Studio past the latest ten", async () => {
    stubJobsApi(
      dialogRoutes({
        runs: Array.from({ length: 11 }, (_, index) =>
          runSummary({ artifact_id: 60 - index, title: `Run ${index}` })
        ),
      })
    )
    renderJobsDialog()

    expect(await screen.findByText("Older runs are in Studio.")).toBeTruthy()
    expect(screen.queryByText("Run 10")).toBeNull()
    expect(screen.getByText("Run 9")).toBeTruthy()
  })

  it("opens a run from the list, and goes back to every job", async () => {
    stubJobsApi({
      ...dialogRoutes({ runs: [runSummary()] }),
      "GET /workspaces/1/job-runs/41": runRead(),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    await user.click(
      await screen.findByRole("button", {
        name: /^Vendor questionnaire \(revised\)/,
      })
    )

    expect(await screen.findByRole("heading", { name: "Done" })).toBeTruthy()
    expect(
      screen.getByRole("heading", { name: "Vendor questionnaire (revised)" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "All jobs" }))
    expect(
      await screen.findByRole("button", { name: "Run Security questionnaire" })
    ).toBeTruthy()
  })

  it("says the jobs could not be read, and reads them again", async () => {
    let fail = true
    stubJobsApi({
      ...dialogRoutes(),
      "GET /job-packs": () =>
        fail
          ? Response.json({ detail: "down" }, { status: 500 })
          : Response.json([TEST_PACK]),
    })
    const user = userEvent.setup()
    renderJobsDialog()

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Could not load your jobs."
    )
    fail = false
    await user.click(screen.getByRole("button", { name: "Try again" }))

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Run Security questionnaire" })
      ).toBeTruthy()
    )
  })
})
