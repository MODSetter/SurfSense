import type {
  Unstable_TriggerMatch,
  Unstable_TriggerMatcher,
} from "@assistant-ui/react"

export const MENTION_TRIGGER = "@"

function isSpace(char: string) {
  return char.trim() === ""
}

/**
 * The mention the caret is in: a word that starts with the trigger, up
 * to the caret. The composer's `@` list and the startup frame both use it,
 * so a word opens the list in one exactly when it does in the other.
 */
export const mentionAt: Unstable_TriggerMatcher = (
  text,
  trigger,
  caret
): Unstable_TriggerMatch | null => {
  let start = caret
  while (start > 0 && !isSpace(text.charAt(start - 1))) start -= 1
  if (!text.startsWith(trigger, start)) return null
  return {
    query: text.slice(start + trigger.length, caret),
    offset: start,
    endOffset: caret,
  }
}
