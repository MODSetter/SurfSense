import { UNSPACED_SCRIPT } from "./join-phrases"

/**
 * The longest start of `text` within `room` characters that ends a word, or
 * any character in Chinese, Japanese or Thai, which do not space their words.
 */
export function clampToRoom(text: string, room: number): string {
  if (text.length <= room) return text
  if (room <= 0) return ""
  let cut = room
  // Never half of a surrogate pair.
  if (/[\uD800-\uDBFF]/.test(text[cut - 1])) cut -= 1
  const edge = text.slice(Math.max(0, cut - 1), cut + 1)
  if (UNSPACED_SCRIPT.test(edge)) return text.slice(0, cut)
  const space = text.slice(0, cut + 1).search(/\s(?=\S*$)/)
  return (space > 0 ? text.slice(0, space) : text.slice(0, cut)).trimEnd()
}
