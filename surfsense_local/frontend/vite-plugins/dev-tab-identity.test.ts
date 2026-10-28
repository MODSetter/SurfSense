import { describe, expect, it } from "vitest"

import { devTabIdentity } from "./dev-tab-identity"

const PAGE = '<head><link rel="icon" href="./favicon.ico" /><title>SurfSense</title></head>'

/** What Vite's dev server makes of a page. */
function served(html: string) {
  const { transformIndexHtml } = devTabIdentity()
  return (transformIndexHtml as (html: string) => string)(html)
}

describe("devTabIdentity", () => {
  it("names the dev server's tab SurfSense Dev, with the DEV icon", () => {
    expect(served(PAGE)).toBe(
      '<head><link rel="icon" href="./favicon-dev.ico" /><title>SurfSense Dev</title></head>'
    )
  })

  it("leaves the build's pages the app's name and icon", () => {
    expect(devTabIdentity().apply).toBe("serve")
  })

  it("leaves a page with its own title and no icon as it is", () => {
    const page = "<head><title>Snapshot</title></head>"

    expect(served(page)).toBe(page)
  })
})
