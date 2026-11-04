import type { TriggerMatch, TriggerMatcher } from "@assistant-ui/react"

export const MENTION_TRIGGER = "@"

function isSpace(char: string) {
  return char.trim() === ""
}

// A chip's text ends so, and the next word can start straight after it.
const CHIP_END = "}"

/**
 * The mention the caret is in: a word that starts with the trigger, up to the
 * caret. The composer's `@` list and the startup frame both use it, so a word
 * opens the list in one exactly when it does in the other.
 */
export const mentionAt: TriggerMatcher = (
  text,
  trigger,
  caret
): TriggerMatch | null => {
  let start = caret
  while (
    start > 0 &&
    !isSpace(text.charAt(start - 1)) &&
    text.charAt(start - 1) !== CHIP_END
  ) {
    start -= 1
  }
  if (!text.startsWith(trigger, start)) return null
  return {
    query: text.slice(start + trigger.length, caret),
    offset: start,
    endOffset: caret,
  }
}

/** As `mentionAt`, and past a space while the words still match a name: "@plan q"
 *  searches on, and a stray `@` in a sentence does not hold the list open. */
export function mentionAmongNames(names: readonly string[]): TriggerMatcher {
  const lowered = names.map((name) => name.toLowerCase())
  return (text, trigger, caret) => {
    const word = mentionAt(text, trigger, caret)
    if (word) return word
    const line = text.lastIndexOf("\n", caret - 1) + 1
    for (
      let start = text.lastIndexOf(trigger, caret - 1);
      start >= line;
      start = text.lastIndexOf(trigger, start - 1)
    ) {
      const before = start > 0 ? text.charAt(start - 1) : " "
      if (!isSpace(before) && before !== CHIP_END) continue
      const query = text.slice(start + trigger.length, caret)
      if (!lowered.some((name) => name.includes(query.toLowerCase()))) {
        return null
      }
      return { query, offset: start, endOffset: caret }
    }
    return null
  }
}
