import { Button } from "@/components/ui/button"
import { useChatCandidates } from "@/features/models/chat-candidates/use-chat-candidates"
import type { ModelSelection } from "@/features/models/selection/api"
import { intl } from "@/i18n/intl"

import { useJobSettings } from "../settings/use-job-settings"

import { displayModelName } from "./model-display-name"

// The provider that runs models on this computer; any other is sent what the
// run reads.
const LOCAL_RUNTIME = "llamacpp"

/** The words for what the models do, from the run form's own messages. */
export type RunModelText = {
  missing: string
  // The selected model, by the name the model picker shows.
  selected: (model: string) => string
  local: string
  remote: string
}

/** The models a run uses, the selected chat model and the job's second check,
 *  and what that means for the documents it reads. */
export function RunModelLines({
  job,
  selection,
  providerAvailable,
  busy,
  onChooseModel,
  text,
}: {
  job: string
  selection: ModelSelection | null
  providerAvailable: boolean
  busy: boolean
  onChooseModel: () => void
  text: RunModelText
}) {
  const candidates = useChatCandidates().data
  const checker = useJobSettings(job).data?.checker ?? null
  const usable = selection !== null && providerAvailable
  const remote =
    (usable && selection.provider !== LOCAL_RUNTIME) ||
    (checker !== null && checker.provider !== LOCAL_RUNTIME)

  const chooseModelButton = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="self-start"
      disabled={busy}
      onClick={onChooseModel}
    >
      {intl.formatMessage({
        id: "jobs_run_model_choose_button",
        defaultMessage: "Choose a model",
      })}
    </Button>
  )

  return (
    <section className="flex flex-col gap-1.5 text-sm">
      {selection === null ? (
        <>
          <p className="text-pretty">{text.missing}</p>
          {chooseModelButton}
        </>
      ) : !providerAvailable ? (
        <>
          <p className="text-pretty">
            {intl.formatMessage(
              {
                id: "jobs_run_model_unusable_body",
                defaultMessage:
                  "{model} can’t be reached right now. Check it in Settings, or choose another.",
              },
              { model: displayModelName(selection.name, candidates) }
            )}
          </p>
          {chooseModelButton}
        </>
      ) : (
        <p>{text.selected(displayModelName(selection.name, candidates))}</p>
      )}
      {checker ? (
        <p>
          {intl.formatMessage(
            {
              id: "jobs_run_checker_label",
              defaultMessage: "Checked again by {model}",
            },
            { model: displayModelName(checker.name, candidates) }
          )}
        </p>
      ) : null}
      {usable && selection.provider === LOCAL_RUNTIME ? (
        <p className="text-pretty text-muted-foreground">{text.local}</p>
      ) : null}
      {remote ? (
        <p className="text-pretty text-muted-foreground">{text.remote}</p>
      ) : null}
    </section>
  )
}
