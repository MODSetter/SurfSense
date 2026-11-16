import { describe, expect, it } from "vitest"

import { guidesUrl, guideUrl } from "./guide-links"

describe("guide links", () => {
  it("open a guide on surfsense.com, tagged with where in the app it was opened", () => {
    const url = new URL(guideUrl("add-sources", "sources_empty", "2.3.1"))

    expect(url.origin + url.pathname).toBe(
      "https://www.surfsense.com/docs/v2/guides/add-sources"
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      utm_source: "desktop",
      utm_medium: "app",
      utm_content: "sources_empty",
      app_version: "2.3.1",
    })
  })

  it("leave the version out until it is read", () => {
    const url = new URL(guidesUrl("about_guides", undefined))

    expect(url.pathname).toBe("/docs/v2/guides")
    expect(url.searchParams.has("app_version")).toBe(false)
  })
})
