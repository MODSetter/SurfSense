import { Autocomplete } from "@base-ui/react/autocomplete"

import {
  ComboboxContent,
  ComboboxInput,
  ComboboxList,
} from "@/components/ui/combobox"

const ITEM_CLASS =
  "flex cursor-default items-center rounded-md py-1 pl-1.5 text-sm outline-hidden select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"

/** A voice from `voices`, or any id typed: a server may voice ones it does not
 *  list, so this suggests rather than restricts, which a combobox would. */
export function VoiceField({
  voices,
  value,
  label,
  placeholder,
  onChange,
}: {
  voices: string[]
  value: string
  label: string
  placeholder: string
  onChange: (voice: string) => void
}) {
  return (
    <Autocomplete.Root
      items={voices}
      value={value}
      onValueChange={(next) => onChange(next)}
      openOnInputClick
      // A chosen voice is the box's text; matching on it would hide the others.
      filter={(voice: string, query: string) =>
        voices.includes(query) ||
        voice.toLowerCase().includes(query.trim().toLowerCase())
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
          {(voice: string) => (
            <Autocomplete.Item key={voice} value={voice} className={ITEM_CLASS}>
              {voice}
            </Autocomplete.Item>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Autocomplete.Root>
  )
}
