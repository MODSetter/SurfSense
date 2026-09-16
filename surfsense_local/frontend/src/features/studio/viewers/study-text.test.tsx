import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { StudyText } from "./study-text"

afterEach(cleanup)

describe("StudyText", () => {
  it("renders plain text as-is", () => {
    render(<StudyText content="Cassini reached Saturn in July 2004." />)
    expect(
      screen.getByText("Cassini reached Saturn in July 2004.")
    ).toBeTruthy()
  })

  it("renders \\(...\\) as inline KaTeX math", () => {
    const { container } = render(<StudyText content="Solve \(x^2 = 4\)." />)
    expect(container.querySelector(".katex")).toBeTruthy()
    expect(container.textContent).toContain("Solve")
  })

  it("falls back to plain text on malformed LaTeX instead of throwing", () => {
    // A plain JS string (not a JSX attribute literal), so the escape needs
    // doubling to keep one literal backslash — JSX attribute strings, unlike
    // regular JS strings, don't process backslash escapes at all.
    const content = "Unbalanced \\(x^2"
    expect(() => render(<StudyText content={content} />)).not.toThrow()
    expect(screen.getByText(content)).toBeTruthy()
  })
})
