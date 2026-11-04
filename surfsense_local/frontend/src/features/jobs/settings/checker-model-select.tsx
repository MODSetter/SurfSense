import { Select } from "@/components/ui/select"
import type { SelectableModel } from "@/features/models/chat-candidates/api"
import { useChatCandidates } from "@/features/models/chat-candidates/use-chat-candidates"
import { modelKey } from "@/features/models/selection/api"
import { intl } from "@/i18n/intl"

import type { ModelRef } from "../api"

// Option values are positions, never a model's key, whose NULs are unsafe in attributes.
const SAME = "same"
const SAVED = "saved"
const option = (index: number) => `c:${index}`

function connections(candidates: readonly SelectableModel[]) {
  const groups = new Map<number, { label: string; indexes: number[] }>()
  candidates.forEach((candidate, index) => {
    if (candidate.connection_id === null) return
    const group = groups.get(candidate.connection_id) ?? {
      label: candidate.connection_label ?? candidate.provider,
      indexes: [],
    }
    group.indexes.push(index)
    groups.set(candidate.connection_id, group)
  })
  return [...groups]
}

/** The model that checks each answer again: the answering one, or any chat model. */
export function CheckerModelSelect({
  id,
  value,
  onChange,
  disabled = false,
}: {
  id: string
  value: ModelRef | null
  onChange: (next: ModelRef | null) => void
  disabled?: boolean
}) {
  const candidates = useChatCandidates().data
  const listed = candidates ?? []
  const chosenIndex = value
    ? listed.findIndex((candidate) => modelKey(candidate) === modelKey(value))
    : -1
  const selected =
    value === null ? SAME : chosenIndex >= 0 ? option(chosenIndex) : SAVED
  const name = (candidate: SelectableModel) =>
    candidate.display_name ?? candidate.name
  const local = listed.flatMap((candidate, index) =>
    candidate.connection_id === null ? [index] : []
  )

  return (
    <Select
      id={id}
      value={selected}
      disabled={disabled || candidates === undefined}
      onChange={(event) => {
        const next = event.target.value
        if (next === SAME) return onChange(null)
        if (next === SAVED) return onChange(value)
        const candidate = listed[Number(next.slice(2))]
        if (candidate)
          onChange({
            provider: candidate.provider,
            connection_id: candidate.connection_id,
            name: candidate.name,
          })
      }}
    >
      <option value={SAME}>
        {intl.formatMessage({
          id: "jobs_settings_checker_same_label",
          defaultMessage: "The answering model",
        })}
      </option>
      {selected === SAVED && value ? (
        <option value={SAVED}>
          {candidates === undefined
            ? value.name
            : intl.formatMessage(
                {
                  id: "jobs_settings_checker_missing_label",
                  defaultMessage: "{model} (not available now)",
                },
                { model: value.name }
              )}
        </option>
      ) : null}
      {local.length > 0 ? (
        <optgroup
          label={intl.formatMessage({
            id: "jobs_settings_checker_local_label",
            defaultMessage: "On this computer",
          })}
        >
          {local.map((index) => (
            <option key={index} value={option(index)}>
              {name(listed[index])}
            </option>
          ))}
        </optgroup>
      ) : null}
      {connections(listed).map(([connectionId, group]) => (
        <optgroup key={connectionId} label={group.label}>
          {group.indexes.map((index) => (
            <option key={index} value={option(index)}>
              {name(listed[index])}
            </option>
          ))}
        </optgroup>
      ))}
    </Select>
  )
}
