import { ResourceUsagePanel } from "./resource-usage-panel"
import { useResourceUsage } from "./use-resource-usage"

/** The panel fed from `GET /system/usage`, polled only while `shown`. */
export function LiveResourceUsage({ shown }: { shown: boolean }) {
  const usage = useResourceUsage(shown)
  return <ResourceUsagePanel usage={usage.data} isError={usage.isError} />
}
