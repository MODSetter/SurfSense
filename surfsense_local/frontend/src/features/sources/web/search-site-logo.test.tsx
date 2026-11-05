import { cleanup } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { render } from "@/test-utils"

import { SEARCH_SITES } from "./search-sites"
import { SearchSiteLogo } from "./search-site-logo"

afterEach(cleanup)

describe("SearchSiteLogo", () => {
  it("draws each site's built-in mark, with no image to load or fail", () => {
    for (const site of SEARCH_SITES) {
      const { container, unmount } = render(<SearchSiteLogo site={site} />)
      expect(container.querySelector("svg")).not.toBeNull()
      expect(container.querySelector("img")).toBeNull()
      unmount()
    }
  })
})
