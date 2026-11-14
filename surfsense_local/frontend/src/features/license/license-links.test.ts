import { describe, expect, it } from "vitest"

import { pricingUrl, supportUrl, trialUrl } from "./license-links"

const TAGS = "utm_source=desktop&utm_medium=app"

describe("license links", () => {
  it("opens pricing for Settings’ trial, beside the free plan", () => {
    expect(trialUrl(undefined)).toBe(
      `https://www.surfsense.com/pricing?${TAGS}&utm_content=license_trial`
    )
  })

  it("opens the downloads page for a job’s trial, where the Business trial is", () => {
    expect(trialUrl(undefined, "jobs_trial")).toBe(
      `https://www.surfsense.com/downloads?${TAGS}&utm_content=jobs_trial`
    )
    expect(trialUrl("2.3.1", "jobs_trial")).toBe(
      `https://www.surfsense.com/downloads?${TAGS}&utm_content=jobs_trial&app_version=2.3.1`
    )
  })

  it("says the Jobs screen sent a visit to pricing", () => {
    expect(pricingUrl("jobs_pricing", "2.3.1")).toBe(
      `https://www.surfsense.com/pricing?${TAGS}&utm_content=jobs_pricing&app_version=2.3.1`
    )
    expect(pricingUrl("license_pricing", undefined)).toBe(
      `https://www.surfsense.com/pricing?${TAGS}&utm_content=license_pricing`
    )
  })

  it("asks support for a job pack file from where the app was", () => {
    expect(supportUrl("jobs_support", undefined)).toBe(
      `https://www.surfsense.com/contact?${TAGS}&utm_content=jobs_support`
    )
    expect(supportUrl("license_jobs_support", "2.3.1")).toBe(
      `https://www.surfsense.com/contact?${TAGS}&utm_content=license_jobs_support&app_version=2.3.1`
    )
  })
})
