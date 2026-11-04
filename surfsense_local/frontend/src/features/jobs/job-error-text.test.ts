import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"

import type { PackOutcome, PackOutcomeCode } from "./api"
import {
  downloadFailureText,
  importErrorText,
  jobsErrorText,
  outcomeText,
} from "./job-error-text"

const refused = (status: number, code: string, detail = {}) =>
  new ApiError(status, "The backend’s own words.", code, {
    code,
    message: "The backend’s own words.",
    ...detail,
  })

const outcome = (code: PackOutcomeCode): PackOutcome => ({
  entitlement: "JOB_QUESTIONNAIRE",
  outcome: code,
  message: "The backend’s own words.",
  version: null,
  detail: null,
})

describe("job error text", () => {
  it("says the license server was not contacted, naming its host", () => {
    expect(
      downloadFailureText(
        refused(403, "egress_disabled", { host: "licenses.example.com" })
      )
    ).toBe(
      "SurfSense didn’t contact its license server, licenses.example.com. Try again and choose Allow, or allow it in Settings › Network."
    )
    // A refusal that names no host is about SurfSense's own server.
    expect(downloadFailureText(refused(403, "egress_disabled"))).toContain(
      "its license server, api.surfsense.com."
    )
  })

  it("words why the download route sent nothing for the license", () => {
    expect(downloadFailureText(refused(409, "license_none"))).toBe(
      "Add a license that includes jobs first."
    )
    expect(downloadFailureText(refused(409, "license_not_active"))).toBe(
      "Your license has ended, or this computer’s clock is behind, so no job can be downloaded."
    )
    expect(downloadFailureText(refused(409, "license_no_jobs"))).toBe(
      "Your license includes no jobs to download."
    )
  })

  it("words every outcome, and none for a job installed or already current", () => {
    const job = "Security questionnaire"

    expect(outcomeText(outcome("installed"), job)).toBeNull()
    expect(outcomeText(outcome("current"), job)).toBeNull()
    expect(
      Object.fromEntries(
        (
          [
            "deferred",
            "job_not_included",
            "pack_not_covered",
            "license_not_valid",
            "license_not_found",
            "needs_newer_app",
            "unknown_job",
            "rate_limited",
            "unavailable",
            "refused",
            "license_outdated",
            "not_written",
          ] as const
        ).map((code) => [code, outcomeText(outcome(code), job)])
      )
    ).toEqual({
      // A deferral with no version: no pack here has the job, and the pack
      // sent for it waits on a run of another job in it.
      deferred:
        "Security questionnaire comes in the same pack as a job whose run was under way, so it waits. SurfSense tries again once the run ends.",
      job_not_included: "Your license doesn’t include Security questionnaire.",
      pack_not_covered:
        "Security questionnaire comes only in a pack with a job your license doesn’t include, so SurfSense’s license server sent nothing. Contact SurfSense support.",
      license_not_valid:
        "SurfSense’s license server didn’t accept this license, so it sent nothing. Check for renewal in Settings › License, or contact SurfSense support.",
      license_not_found:
        "SurfSense’s license server has no license with this key.",
      needs_newer_app:
        "Security questionnaire needs a newer version of SurfSense. Update the app, then download it again.",
      unknown_job:
        "SurfSense’s license server has no download for Security questionnaire.",
      rate_limited:
        "Jobs were downloaded too often with this license. Try again in an hour.",
      unavailable:
        "SurfSense’s license server couldn’t send Security questionnaire. Try again later.",
      refused:
        "The download of Security questionnaire didn’t pass SurfSense’s checks, so it wasn’t installed.",
      license_outdated:
        "Your license has changed on SurfSense’s license server. Check for renewal in Settings › License, then download Security questionnaire again.",
      not_written:
        "SurfSense couldn’t save Security questionnaire on this computer. Check that the disk has room, then try again.",
    })
    // With a version, the one installed here: a run held back the check.
    expect(outcomeText({ ...outcome("deferred"), version: "0.4.3" }, job)).toBe(
      "A run of Security questionnaire was under way, so any newer version waits. SurfSense checks again once the run ends."
    )
  })

  it("words a refused pack file by its code", () => {
    const text = (code: string, status = 422) =>
      importErrorText(refused(status, code))

    for (const code of ["NOT_A_PACK", "BAD_MANIFEST", "BAD_PATH"])
      expect(text(code)).toBe(
        "This file isn’t a SurfSense job pack. Choose the job pack’s .zip file."
      )
    // A file past 50 MB is refused before it is sent, so this is a small zip
    // holding more files, or more once extracted, than any pack does.
    expect(text("PACK_TOO_LARGE", 413)).toBe(
      "This file isn’t a SurfSense job pack. Choose the job pack’s .zip file."
    )
    for (const code of [
      "PACK_NOT_SIGNED",
      "PACK_BAD_SIGNATURE",
      "PACK_FILE_UNLISTED",
      "PACK_FILE_MISSING",
      "PACK_FILE_CHANGED",
    ])
      expect(text(code)).toBe(
        "This job pack was changed after SurfSense signed it, or SurfSense didn’t sign it, so it can’t be used."
      )
    expect(text("NEEDS_NEWER_APP")).toBe(
      "This job pack needs a newer version of SurfSense. Update the app, then import it again."
    )
    expect(text("PACK_OLDER", 409)).toBe(
      "A newer version of this job is already installed."
    )
    expect(text("PACK_IN_USE", 409)).toBe(
      "A run of this job is still going. Import the pack once it finishes."
    )
    expect(text("PACK_VERSION_TAKEN", 409)).toBe(
      "A different copy of this version is already installed. Import a newer version instead."
    )
    expect(text("PACK_NOT_WRITTEN", 500)).toBe(
      "SurfSense couldn’t save the pack on this computer. Check that the disk has room, then try again."
    )
  })

  it("names a job no longer on this computer", () => {
    expect(jobsErrorText(refused(404, "NOT_FOUND"))).toBe(
      "This job is no longer on this computer."
    )
  })

  it("shows the backend’s sentence for a code it has no words for", () => {
    for (const code of [
      "JOB_RUN_REFUSED",
      "BAD_JOB_SETTINGS",
      "BAD_JOB_CONFIG",
      "SOMETHING_NEW",
    ])
      expect(jobsErrorText(refused(409, code))).toBe("The backend’s own words.")
    expect(importErrorText(refused(422, "BAD_JOB_CONFIG"))).toBe(
      "The backend’s own words."
    )
    expect(downloadFailureText(refused(422, "something_new"))).toBe(
      "The backend’s own words."
    )
    expect(
      outcomeText(
        { ...outcome("installed"), outcome: "brand_new" as PackOutcomeCode },
        "Security questionnaire"
      )
    ).toBe("The backend’s own words.")
  })

  it("uses Studio’s words for a run that cannot be stopped or run again", () => {
    expect(jobsErrorText(refused(409, "nothing_running"))).toBe(
      "Nothing is running."
    )
  })

  it("says something went wrong when nothing says what", () => {
    expect(jobsErrorText(new ApiError(500, "", null))).toBe(
      "Something went wrong. Try again."
    )
    expect(downloadFailureText("not an error")).toBe(
      "Something went wrong. Try again."
    )
  })
})
