import { ResourceUsagePanel } from "./resource-usage-panel"
import { useResourceUsage } from "./use-resource-usage"

/** The panel fed from `GET /system/usage`, polled while it is mounted. */
export function LiveResourceUsage() {
  const usage = useResourceUsage()
  return <ResourceUsagePanel usage={usage.data} isError={usage.isError} />
}
