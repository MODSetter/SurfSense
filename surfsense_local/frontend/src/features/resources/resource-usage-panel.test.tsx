import { cleanup, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { render } from "@/test-utils"

import type { ResourceUsage } from "./api"
import { ResourceUsagePanel } from "./resource-usage-panel"

const GIB = 1024 ** 3
const MIB = 1024 ** 2

// The Windows test machine with a chat model loaded: an RTX 3080, llama.cpp
// holding 5.5 GB of its memory, a browser most of the rest.
const LOADED: ResourceUsage = {
  cpu: { percent: 23, app_percent: 12 },
  memory: {
    total_bytes: 16 * GIB,
    used_bytes: 9.8 * GIB,
    app_bytes: 3.1 * GIB,
  },
  gpus: [
    {
      name: "NVIDIA GeForce RTX 3080",
      unified_memory: false,
      memory: {
        total_bytes: 9.8 * GIB,
        used_bytes: 7.2 * GIB,
        app_bytes: 5.5 * GIB,
      },
      load: { percent: 41, app_percent: 38 },
    },
  ],
  engines: [
    {
      engine: "llamacpp",
      processes: 2,
      cpu_percent: 9,
      memory_bytes: 1.2 * GIB,
      gpu_memory_bytes: 5.5 * GIB,
      gpu_percent: 38,
    },
    {
      engine: "sdcpp",
      processes: 0,
      cpu_percent: 0,
      memory_bytes: 0,
      gpu_memory_bytes: 0,
      gpu_percent: 0,
    },
    {
      engine: "audiocpp",
      processes: 1,
      cpu_percent: 0,
      memory_bytes: 12 * MIB,
      gpu_memory_bytes: 0,
      gpu_percent: 0,
    },
    {
      engine: "backend",
      processes: 6,
      cpu_percent: 2,
      memory_bytes: 1.6 * GIB,
      gpu_memory_bytes: 0,
      gpu_percent: 0,
    },
    {
      engine: "interface",
      processes: 4,
      cpu_percent: 1,
      memory_bytes: 300 * MIB,
      gpu_memory_bytes: 90 * MIB,
      gpu_percent: 0,
    },
  ],
}

function meter(name: string) {
  return screen.getByRole("meter", { name })
}

afterEach(cleanup)

describe("resource usage panel", () => {
  it("shows the machine's figure and the app's share for each resource", () => {
    render(<ResourceUsagePanel usage={LOADED} isError={false} />)

    const ram = meter("RAM")
    expect(ram.getAttribute("aria-valuetext")).toBe(
      "9.8 GB of 16.0 GB in use. SurfSense is using 3.1 GB."
    )
    expect(within(ram.closest("[data-row]")!).getByText("3.1 GB")).toBeTruthy()
    expect(meter("VRAM").getAttribute("aria-valuetext")).toBe(
      "7.2 GB of 9.8 GB in use. SurfSense is using 5.5 GB."
    )
    expect(meter("CPU").getAttribute("aria-valuetext")).toBe(
      "23% busy. SurfSense is using 12%."
    )
    expect(meter("GPU").getAttribute("aria-valuetext")).toBe(
      "41% busy. SurfSense is using 38%."
    )
  })

  it("splits each bar into the app's share, other apps and free", () => {
    render(<ResourceUsagePanel usage={LOADED} isError={false} />)

    const segments =
      meter("VRAM").querySelectorAll<HTMLElement>("[data-segment]")
    const widths = Object.fromEntries(
      [...segments].map((s) => [s.dataset.segment, parseFloat(s.style.width)])
    )
    expect(widths.app).toBeCloseTo((5.5 / 9.8) * 100)
    expect(widths.other).toBeCloseTo(((7.2 - 5.5) / 9.8) * 100)
  })

  it("lists each engine without a toggle, and says which ones are not running", () => {
    render(<ResourceUsagePanel usage={LOADED} isError={false} />)
    expect(screen.queryByRole("button")).toBeNull()

    const table = screen.getByRole("table")
    const llama = within(table).getByRole("row", { name: /llama\.cpp/ })
    expect(within(llama).getByText("1.2 GB")).toBeTruthy()
    expect(within(llama).getByText("5.5 GB")).toBeTruthy()
    const sd = within(table).getByRole("row", { name: /stable-diffusion\.cpp/ })
    expect(within(sd).getByText("Not running")).toBeTruthy()
    const shell = within(table).getByRole("row", { name: /Interface/ })
    expect(within(shell).getByText("300 MB")).toBeTruthy()
  })

  it("says unknown rather than zero where the system cannot attribute graphics memory", () => {
    const amd = {
      ...LOADED,
      gpus: [
        {
          ...LOADED.gpus[0],
          name: "AMD GPU",
          memory: { ...LOADED.gpus[0].memory, app_bytes: null },
          load: { percent: 41, app_percent: null },
        },
      ],
    }

    render(<ResourceUsagePanel usage={amd} isError={false} />)

    expect(meter("VRAM").getAttribute("aria-valuetext")).toBe(
      "7.2 GB of 9.8 GB in use. SurfSense’s share isn’t reported on this system."
    )
  })

  it("shows no graphics rows on a machine without a card", () => {
    render(
      <ResourceUsagePanel usage={{ ...LOADED, gpus: [] }} isError={false} />
    )

    expect(screen.queryByRole("meter", { name: "VRAM" })).toBeNull()
    expect(screen.queryByRole("meter", { name: "GPU" })).toBeNull()
    expect(meter("RAM")).toBeTruthy()
  })

  it("reads a unified-memory GPU as busy only, its memory already in RAM", () => {
    const mac = {
      ...LOADED,
      gpus: [
        {
          name: "Apple M2",
          unified_memory: true,
          memory: {
            total_bytes: 16 * GIB,
            used_bytes: 2.5 * GIB,
            app_bytes: null,
          },
          load: { percent: 12, app_percent: null },
        },
      ],
    }

    render(<ResourceUsagePanel usage={mac} isError={false} />)

    expect(screen.queryByRole("meter", { name: "VRAM" })).toBeNull()
    expect(meter("GPU")).toBeTruthy()
  })

  it("heads each part: the whole machine, SurfSense by engine, and the graphics cards", () => {
    render(<ResourceUsagePanel usage={LOADED} isError={false} />)

    const machine = screen.getByRole("region", { name: "This computer" })
    expect(within(machine).getByRole("meter", { name: "RAM" })).toBeTruthy()
    const engines = screen.getByRole("region", { name: "By engine" })
    expect(within(engines).getByRole("table")).toBeTruthy()
    const graphics = screen.getByRole("region", { name: "Graphics" })
    expect(within(graphics).getByText("NVIDIA GeForce RTX 3080")).toBeTruthy()
    expect(within(graphics).getByText("9.8 GB of its own memory")).toBeTruthy()
    expect(screen.getAllByRole("separator")).toHaveLength(2)
  })

  it("numbers the cards as the GPU rows do, so each name matches its bars", () => {
    const twoCards = {
      ...LOADED,
      gpus: [
        LOADED.gpus[0],
        { ...LOADED.gpus[0], name: "AMD Radeon RX 6500 XT" },
      ],
    }

    render(<ResourceUsagePanel usage={twoCards} isError={false} />)

    const graphics = screen.getByRole("region", { name: "Graphics" })
    const second = within(graphics).getByText("AMD Radeon RX 6500 XT")
    expect(second.closest("li")?.textContent).toContain("GPU 2")
  })

  it("says a unified-memory card shares the CPU's memory", () => {
    const mac = {
      ...LOADED,
      gpus: [{ ...LOADED.gpus[0], name: "Apple M2", unified_memory: true }],
    }

    render(<ResourceUsagePanel usage={mac} isError={false} />)

    const graphics = screen.getByRole("region", { name: "Graphics" })
    expect(
      within(graphics).getByText("Shares memory with the CPU")
    ).toBeTruthy()
  })

  it("leaves out the graphics section on a machine without a card", () => {
    render(
      <ResourceUsagePanel usage={{ ...LOADED, gpus: [] }} isError={false} />
    )

    expect(screen.queryByRole("region", { name: "Graphics" })).toBeNull()
    expect(screen.getAllByRole("separator")).toHaveLength(1)
  })

  it("says so when usage cannot be read", () => {
    render(<ResourceUsagePanel usage={undefined} isError />)

    expect(screen.getByText("Usage unavailable")).toBeTruthy()
  })
})
