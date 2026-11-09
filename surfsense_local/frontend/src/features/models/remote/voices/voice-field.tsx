import { Autocomplete } from "@base-ui/react/autocomplete"

import {
  ComboboxContent,
  ComboboxInput,
  ComboboxList,
} from "@/components/ui/combobox"

import type { VoiceOption } from "./api"

const ITEM_CLASS =
  "flex cursor-default items-center rounded-md py-1 pl-1.5 text-sm outline-hidden select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"

/** A voice from `voices`, or any id typed: a server may voice ones it does not
 *  list, so this suggests rather than restricts, which a combobox would. It shows
 *  a voice's name and hands over its id. */
export function VoiceField({
  voices,
  value,
  label,
  placeholder,
  onChange,
}: {
  voices: VoiceOption[]
  /** The voice's id, or the text being typed. */
  value: string
  label: string
  placeholder: string
  onChange: (voice: string) => void
}) {
  const labels = voices.map((voice) => voice.label)
  return (
    <Autocomplete.Root
      items={labels}
      value={voices.find((voice) => voice.id === value)?.label ?? value}
      onValueChange={(next) =>
        onChange(voices.find((voice) => voice.label === next)?.id ?? next)
      }
      openOnInputClick
      // A chosen voice is the box's text; matching on it would hide the others.
      filter={(name: string, query: string) =>
        labels.includes(query) ||
        name.toLowerCase().includes(query.trim().toLowerCase())
      }
    >
      <ComboboxInput
        aria-label={label}
        placeholder={placeholder}
        className="w-full select-text"
        maxLength={100}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
      />
      {/* An id no voice matches leaves nothing to show. */}
      <ComboboxContent className="data-empty:hidden">
        <ComboboxList>
          {(name: string) => (
            <Autocomplete.Item key={name} value={name} className={ITEM_CLASS}>
              {name}
            </Autocomplete.Item>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Autocomplete.Root>
  )
}
