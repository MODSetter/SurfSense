import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { FieldLabel } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { AllJobsButton } from "../all-jobs-button"
import type { JobSettings, ModelRef } from "../api"
import { jobsErrorText } from "../job-error-text"

import { CheckerModelSelect } from "./checker-model-select"
import { useJobSettings, useSaveJobSettings } from "./use-job-settings"

type Draft = { values: Record<string, boolean>; checker: ModelRef | null }

const asSaved = (read: JobSettings): Draft => ({
  values: Object.fromEntries(
    read.settings.map((setting) => [setting.key, setting.value])
  ),
  checker: read.checker,
})

/** The firm's choices for every run of a job: the pack's own switches, and
 *  which model makes the second check. Saved whole. */
export function JobSettingsForm({
  job,
  title,
  onBack,
}: {
  job: string
  title: string
  onBack: () => void
}) {
  const read = useJobSettings(job)
  const save = useSaveJobSettings(job)
  const checkerId = useId()
  // Null while it matches what is saved.
  const [draft, setDraft] = useState<Draft | null>(null)
  const shown = draft ?? (read.data ? asSaved(read.data) : null)

  const edit = (next: Draft) => {
    save.reset()
    setDraft(next)
  }

  let body
  if (read.isPending) {
    body = (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-56" />
        <Skeleton className="h-5 w-48" />
      </div>
    )
  } else if (read.error || !read.data || !shown) {
    body = (
      <p role="alert" className="text-sm text-destructive">
        {read.error instanceof ApiError && read.error.code === "NOT_FOUND"
          ? jobsErrorText(read.error)
          : intl.formatMessage({
              id: "jobs_settings_load_error",
              defaultMessage: "Could not load this job’s settings.",
            })}
      </p>
    )
  } else {
    body = (
      <>
        {read.data.settings.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {read.data.settings.map((setting) => (
              <li
                key={setting.key}
                className="flex items-start justify-between gap-6"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{setting.label}</span>
                  <span className="text-sm text-pretty text-muted-foreground">
                    {setting.description}
                  </span>
                </div>
                <Switch
                  checked={shown.values[setting.key] ?? setting.value}
                  aria-label={setting.label}
                  disabled={save.isPending}
                  onCheckedChange={(checked) =>
                    edit({
                      ...shown,
                      values: { ...shown.values, [setting.key]: checked },
                    })
                  }
                />
              </li>
            ))}
          </ul>
        ) : null}
        {read.data.checks ? (
          <section className="flex flex-col gap-2">
            <FieldLabel htmlFor={checkerId}>
              {intl.formatMessage({
                id: "jobs_settings_checker_label",
                defaultMessage: "Second check",
              })}
            </FieldLabel>
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "jobs_settings_checker_body",
                defaultMessage:
                  "SurfSense checks each answer a second time before writing it. Another model can make that check; one that doesn’t run on this computer receives each question and its passages.",
              })}
            </p>
            <CheckerModelSelect
              id={checkerId}
              value={shown.checker}
              disabled={save.isPending}
              onChange={(checker) => edit({ ...shown, checker })}
            />
          </section>
        ) : null}
        {save.error ? (
          <p role="alert" className="text-sm text-pretty text-destructive">
            {jobsErrorText(save.error)}
          </p>
        ) : null}
        <div className="flex items-center justify-end gap-3">
          {save.isSuccess && draft === null ? (
            <p role="status" className="text-sm text-muted-foreground">
              {intl.formatMessage({
                id: "jobs_settings_saved_status",
                defaultMessage: "Saved",
              })}
            </p>
          ) : null}
          <Button
            type="button"
            disabled={draft === null || save.isPending}
            onClick={() =>
              save.mutate(
                { settings: shown.values, checker: shown.checker },
                { onSuccess: () => setDraft(null) }
              )
            }
          >
            {save.isPending ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "jobs_settings_save_button",
              defaultMessage: "Save",
            })}
          </Button>
        </div>
      </>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <AllJobsButton onClick={onBack} disabled={save.isPending} />
        <h3 className="text-base font-medium text-balance">
          {intl.formatMessage(
            { id: "jobs_settings_title", defaultMessage: "{job} settings" },
            { job: title }
          )}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "jobs_settings_body",
            defaultMessage:
              "Your firm’s choices for every run of this job. A change applies to the runs you start after it.",
          })}
        </p>
      </div>
      {body}
    </div>
  )
}
