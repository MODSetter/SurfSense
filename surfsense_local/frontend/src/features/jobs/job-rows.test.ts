import { describe, expect, it } from "vitest"

import type { PackInfo } from "./api"
import { jobRows } from "./job-rows"
import {
  BUSINESS,
  BUSINESS_TRIAL,
  INDIVIDUAL,
  NO_LICENSE,
  TEST_JOB,
  TEST_PACK,
  TRIAL,
  lockedPack,
} from "./stub-jobs-api"

const ended = (license: typeof BUSINESS) =>
  ({ ...license, state: "license_expired" }) as const

describe("job rows", () => {
  it("offers a job no license here includes as a trial, beside adding a license", () => {
    const [row] = jobRows([], NO_LICENSE)

    expect(row).toMatchObject({
      key: "JOB_QUESTIONNAIRE",
      entitlement: "JOB_QUESTIONNAIRE",
      job: null,
      name: "Security questionnaire",
      version: null,
      kind: "locked_none",
    })
    expect(row.description).toContain("security questionnaire workbook")
    expect(jobRows([lockedPack("none")], NO_LICENSE)[0]).toMatchObject({
      job: "test-questionnaire",
      version: "0.4.3",
      kind: "locked_none",
    })
  })

  it("tells a trial license without the job that Business includes it", () => {
    expect(jobRows([], TRIAL)[0].kind).toBe("locked_trial")
    expect(jobRows([lockedPack("not_included")], TRIAL)[0].kind).toBe(
      "locked_trial"
    )
  })

  it("sends an Individual license to its renewal check, never to a trial", () => {
    expect(jobRows([], INDIVIDUAL)[0].kind).toBe("locked_paid")
    expect(jobRows([lockedPack("not_included")], INDIVIDUAL)[0].kind).toBe(
      "locked_paid"
    )
    // A hand-issued Business license without the code is paid too.
    expect(jobRows([], { ...BUSINESS, jobs: [] })[0].kind).toBe("locked_paid")
  })

  it("offers an ended trial pricing and a replaced license", () => {
    expect(jobRows([], ended(BUSINESS_TRIAL))[0].kind).toBe("trial_ended")
    expect(
      jobRows([lockedPack("expired")], ended(BUSINESS_TRIAL))[0].kind
    ).toBe("trial_ended")
  })

  it("sends an ended Business license to its renewal check, installed or not", () => {
    expect(jobRows([], ended(BUSINESS))[0].kind).toBe("expired")
    expect(jobRows([lockedPack("expired")], ended(BUSINESS))[0].kind).toBe(
      "expired"
    )
  })

  it("lets a license that includes the job run the installed one", () => {
    expect(jobRows([TEST_PACK], BUSINESS)).toEqual([
      expect.objectContaining({
        key: "JOB_QUESTIONNAIRE",
        job: "test-questionnaire",
        name: "Security questionnaire",
        version: "0.4.3",
        kind: "available",
      }),
    ])
  })

  it("offers a download for a job the license includes but this computer lacks", () => {
    expect(jobRows([], BUSINESS)[0]).toMatchObject({
      job: null,
      kind: "not_downloaded",
    })
    expect(jobRows([], BUSINESS_TRIAL)[0].kind).toBe("not_downloaded")
  })

  it("holds a job while the clock is behind", () => {
    const clock = { ...BUSINESS, state: "clock_untrusted" } as const
    expect(jobRows([], clock)[0].kind).toBe("clock")
    expect(jobRows([lockedPack("clock")], clock)[0].kind).toBe("clock")
  })

  it("names no license for an installed paid job that carries no code", () => {
    const pack = lockedPack("no_entitlement", { entitlement: null })

    expect(jobRows([pack], BUSINESS)).toEqual([
      expect.objectContaining({
        key: "JOB_QUESTIONNAIRE",
        kind: "not_downloaded",
      }),
      expect.objectContaining({
        key: "job:test-questionnaire",
        entitlement: null,
        job: "test-questionnaire",
        name: "Test questionnaire",
        kind: "no_entitlement",
      }),
    ])
  })

  it("lists an installed job this version has no name for by its pack’s name", () => {
    const other: PackInfo = {
      ...TEST_PACK,
      id: "other-pack",
      version: "1.2.0",
      jobs: [
        {
          ...TEST_JOB,
          key: "zz-job",
          name: "Zebra review",
          description: "Reviews zebras.",
          entitlement: "JOB_ZEBRA",
        },
        {
          ...TEST_JOB,
          key: "aa-job",
          name: "Audit letter",
          description: "Writes audit letters.",
          entitlement: "JOB_AUDIT",
        },
      ],
    }

    const rows = jobRows([other], { ...BUSINESS, jobs: ["JOB_AUDIT"] })

    expect(rows.map((row) => row.name)).toEqual([
      "Security questionnaire",
      "Audit letter",
      "Zebra review",
    ])
    expect(rows[1]).toMatchObject({
      key: "JOB_AUDIT",
      job: "aa-job",
      description: "Writes audit letters.",
      version: "1.2.0",
      kind: "available",
    })
  })

  it("lists a license’s job this version does not know by its code", () => {
    const rows = jobRows([], {
      ...BUSINESS,
      jobs: ["JOB_QUESTIONNAIRE", "JOB_NEW", "JOB_NEW"],
    })

    expect(rows).toHaveLength(2)
    expect(rows[1]).toMatchObject({
      key: "JOB_NEW",
      entitlement: "JOB_NEW",
      name: "JOB_NEW",
      description: null,
      kind: "not_downloaded",
    })
  })

  it("takes the unlocked job over a locked one for the same code", () => {
    const newer: PackInfo = {
      ...TEST_PACK,
      id: "test-pack-two",
      version: "0.5.0",
      jobs: [{ ...TEST_JOB, key: "test-questionnaire-two" }],
    }

    expect(jobRows([lockedPack("expired"), newer], BUSINESS)[0]).toMatchObject({
      job: "test-questionnaire-two",
      version: "0.5.0",
      // Each pack’s, which a check a run held back may name.
      versions: ["0.4.3", "0.5.0"],
      kind: "available",
    })
  })
})
