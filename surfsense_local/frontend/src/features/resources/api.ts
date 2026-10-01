import { requestJson } from "@/lib/api"

// Mirrors surfsense_local/backend/modules/resource_usage/schemas.py.
export type EngineName =
  "llamacpp" | "sdcpp" | "audiocpp" | "backend" | "interface"

export type Meter = {
  total_bytes: number
  // Everything in use, the app's share included.
  used_bytes: number
  // Null where the system cannot attribute usage to processes.
  app_bytes: number | null
}

export type Load = {
  percent: number | null
  app_percent: number | null
}

export type GpuUsage = {
  name: string
  // Apple Silicon: the memory is system RAM, already in `memory`.
  unified_memory: boolean
  memory: Meter
  load: Load
}

export type EngineUsage = {
  engine: EngineName
  processes: number
  // A share of the whole machine, not of one core.
  cpu_percent: number
  memory_bytes: number
  gpu_memory_bytes: number | null
  gpu_percent: number | null
}

export type ResourceUsage = {
  cpu: Load
  memory: Meter
  gpus: GpuUsage[]
  engines: EngineUsage[]
}

export async function getResourceUsage(
  signal?: AbortSignal
): Promise<ResourceUsage> {
  const body = await requestJson<unknown>("/system/usage", { signal })
  // A side panel on every workspace: a body it cannot read shows as
  // unavailable rather than taking the dashboard down with it.
  if (!isResourceUsage(body)) throw new Error("unreadable resource usage")
  return body
}

function isResourceUsage(body: unknown): body is ResourceUsage {
  if (typeof body !== "object" || body === null) return false
  const usage = body as Record<string, unknown>
  return (
    typeof usage.cpu === "object" &&
    usage.cpu !== null &&
    typeof usage.memory === "object" &&
    usage.memory !== null &&
    Array.isArray(usage.gpus) &&
    Array.isArray(usage.engines)
  )
}
