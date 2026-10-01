import { intl } from "@/i18n/intl"

import type { GpuUsage } from "./api"
import { GIB } from "./format-usage"
import { gpuLabel } from "./usage-rows"

/** Names each card the GPU rows measure, numbered the same way. */
export function GraphicsCards({ gpus }: { gpus: GpuUsage[] }) {
  const numbered = gpus.length > 1
  return (
    <ul className="flex flex-col gap-2">
      {gpus.map((gpu, index) => (
        <li key={index} className="flex items-baseline gap-2">
          {numbered ? (
            <span className="text-muted-foreground">
              {gpuLabel(true, index)}
            </span>
          ) : null}
          <span className="font-medium">{gpu.name}</span>
          <span className="text-muted-foreground">
            {gpu.unified_memory
              ? intl.formatMessage({
                  id: "resources_graphics_unified_body",
                  defaultMessage: "Shares memory with the CPU",
                })
              : intl.formatMessage(
                  {
                    id: "resources_graphics_dedicated_body",
                    defaultMessage:
                      "{size, number, ::unit/gigabyte .0} of its own memory",
                  },
                  { size: gpu.memory.total_bytes / GIB }
                )}
          </span>
        </li>
      ))}
    </ul>
  )
}
