import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ModelIssueNotice } from "./model-issue-notice"

describe("ModelIssueNotice", () => {
  it("says a Claude Code too old for the plan has to be updated", () => {
    render(
      <ModelIssueNotice
        issue={{ model: "claude-sonnet-5-5", code: "claude_too_old" }}
        onOpenSettings={vi.fn()}
      />
    )

    expect(screen.getByRole("status").textContent).toContain(
      "Claude Code is too old. Update it."
    )
  })
})
