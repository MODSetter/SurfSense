import type { ModelType } from "../../model-type"
import { InstallProgress } from "../chat/install-progress"
import { jobsFor } from "./job-state"
import { useInstall } from "./use-install"

/** The downloads whose model can fill `slot`, wherever they were started. */
export function usePendingInstalls(slot: ModelType) {
  const { installs, cancel } = useInstall({ select: false })
  const jobs = jobsFor(installs, slot)
  if (jobs.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      {jobs.map((job) => (
        <div key={job.id} className="flex flex-col gap-2">
          <p className="truncate text-sm font-medium">{job.label}</p>
          <InstallProgress event={job.event} onCancel={() => cancel(job.id)} />
        </div>
      ))}
    </div>
  )
}
