import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./tooltip"

afterEach(cleanup)

describe("Tooltip accessibility", () => {
  it("connects the trigger to tooltip content via aria-describedby and assigns role='tooltip'", () => {
    render(
      <TooltipProvider>
        <Tooltip defaultOpen>
          <TooltipTrigger render={<button type="button">Hover me</button>} />
          <TooltipContent>Detailed helper information</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const trigger = screen.getByRole("button", { name: "Hover me" })
    const describedBy = trigger.getAttribute("aria-describedby")
    expect(describedBy).toBeTruthy()

    const popup = document.getElementById(describedBy!)
    expect(popup).not.toBeNull()
    expect(popup?.getAttribute("role")).toBe("tooltip")
    expect(popup?.textContent).toContain("Detailed helper information")
    expect(
      screen.getByRole("button", {
        name: "Hover me",
        description: "Detailed helper information",
      })
    ).toBe(trigger)
  })

  it("merges existing aria-describedby on the trigger", () => {
    render(
      <TooltipProvider>
        <div id="existing-desc">Existing explanation</div>
        <Tooltip defaultOpen>
          <TooltipTrigger
            aria-describedby="existing-desc"
            render={<button type="button">Action</button>}
          />
          <TooltipContent>Tooltip explanation</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const trigger = screen.getByRole("button", { name: "Action" })
    const describedBy = trigger.getAttribute("aria-describedby")
    expect(describedBy).toContain("existing-desc")

    const ids = describedBy!.split(/\s+/)
    expect(ids.length).toBe(2)
    expect(ids[0]).toBe("existing-desc")

    const tooltipElement = document.getElementById(ids[1])
    expect(tooltipElement).not.toBeNull()
    expect(tooltipElement?.getAttribute("role")).toBe("tooltip")
    expect(tooltipElement?.textContent).toContain("Tooltip explanation")
  })

  it("supports custom id on TooltipContent", () => {
    render(
      <TooltipProvider>
        <Tooltip defaultOpen>
          <TooltipTrigger render={<button type="button">Trigger</button>} />
          <TooltipContent id="custom-tooltip-id">
            Custom ID content
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )

    const trigger = screen.getByRole("button", { name: "Trigger" })
    expect(trigger.getAttribute("aria-describedby")).toBe("custom-tooltip-id")
    const popup = document.getElementById("custom-tooltip-id")
    expect(popup).not.toBeNull()
    expect(popup?.getAttribute("role")).toBe("tooltip")
    expect(popup?.textContent).toContain("Custom ID content")
  })
})
