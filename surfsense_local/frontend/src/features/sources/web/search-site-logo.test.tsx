import { cleanup, fireEvent } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { render } from "@/test-utils"

import { SearchSiteLogo } from "./search-site-logo"

afterEach(cleanup)

describe("SearchSiteLogo", () => {
  it("tries the next site's logo after the last one failed", () => {
    const { container, rerender } = render(<SearchSiteLogo site="reddit" />)
    fireEvent.error(container.querySelector("img") as HTMLImageElement)
    expect(container.querySelector("img")).toBeNull()

    rerender(<SearchSiteLogo site="instagram" />)

    expect(container.querySelector("img")).not.toBeNull()
  })
})
