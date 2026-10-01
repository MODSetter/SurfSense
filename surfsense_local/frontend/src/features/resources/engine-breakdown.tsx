import { intl } from "@/i18n/intl"

import type { EngineName, EngineUsage, ResourceUsage } from "./api"
import { formatMemory, formatPercent } from "./format-usage"

// The runtimes' own names, which are not translated.
const RUNTIME_NAMES: Partial<Record<EngineName, string>> = {
  llamacpp: "llama.cpp",
  sdcpp: "stable-diffusion.cpp",
  audiocpp: "audio.cpp",
}

function engineName(engine: EngineName): string {
  if (engine === "backend") {
    return intl.formatMessage({
      id: "resources_engine_backend_label",
      defaultMessage: "Backend",
    })
  }
  if (engine === "interface") {
    return intl.formatMessage({
      id: "resources_engine_interface_label",
      defaultMessage: "Interface",
    })
  }
  return RUNTIME_NAMES[engine] ?? engine
}

/** Each part of the app on its own row: what each runtime is holding right now. */
export function EngineBreakdown({
  id,
  usage,
}: {
  id: string
  usage: ResourceUsage
}) {
  // Unified memory is already in each process's RAM, so it has no column.
  const showVram = usage.gpus.some((gpu) => !gpu.unified_memory)
  const columns = showVram ? 3 : 2
  const cards = usage.gpus.map((gpu) => gpu.name)

  return (
    <div id={id} className="mt-3 border-t pt-2.5">
      <table className="w-full table-fixed text-left tabular-nums">
        <colgroup>
          <col />
          <col className="w-12" />
          <col className="w-16" />
          {showVram ? <col className="w-16" /> : null}
        </colgroup>
        <thead className="text-secondary-foreground">
          <tr>
            <th scope="col" className="pb-1 font-normal">
              <span className="sr-only">
                {intl.formatMessage({
                  id: "resources_breakdown_engine_label",
                  defaultMessage: "Engine",
                })}
              </span>
            </th>
            <th scope="col" className="pb-1 text-right font-normal">
              {intl.formatMessage({
                id: "resources_breakdown_cpu_label",
                defaultMessage: "CPU",
              })}
            </th>
            <th scope="col" className="pb-1 text-right font-normal">
              {intl.formatMessage({
                id: "resources_breakdown_ram_label",
                defaultMessage: "RAM",
              })}
            </th>
            {showVram ? (
              <th scope="col" className="pb-1 text-right font-normal">
                {intl.formatMessage({
                  id: "resources_breakdown_vram_label",
                  defaultMessage: "VRAM",
                })}
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {usage.engines.map((engine) => (
            <EngineRow
              key={engine.engine}
              engine={engine}
              columns={columns}
              showVram={showVram}
            />
          ))}
        </tbody>
      </table>
      {cards.length > 0 ? (
        <p className="mt-2 truncate text-secondary-foreground">
          {intl.formatList(cards, { type: "conjunction" })}
        </p>
      ) : null}
    </div>
  )
}

function EngineRow({
  engine,
  columns,
  showVram,
}: {
  engine: EngineUsage
  columns: number
  showVram: boolean
}) {
  const name = engineName(engine.engine)
  if (engine.processes === 0) {
    return (
      <tr className="text-secondary-foreground">
        <th scope="row" className="truncate py-0.5 font-normal">
          {name}
        </th>
        <td colSpan={columns} className="py-0.5 text-right">
          {intl.formatMessage({
            id: "resources_engine_not_running_status",
            defaultMessage: "Not running",
          })}
        </td>
      </tr>
    )
  }
  return (
    <tr className="text-foreground">
      <th scope="row" className="truncate py-0.5 font-medium">
        {name}
      </th>
      <td className="py-0.5 text-right">{formatPercent(engine.cpu_percent)}</td>
      <td className="py-0.5 text-right">{formatMemory(engine.memory_bytes)}</td>
      {showVram ? (
        <td className="py-0.5 text-right">
          {engine.gpu_memory_bytes === null
            ? "—"
            : formatMemory(engine.gpu_memory_bytes)}
        </td>
      ) : null}
    </tr>
  )
}
