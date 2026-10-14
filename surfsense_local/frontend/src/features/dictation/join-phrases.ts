export type TranscribedPhrase = { text: string; language: string | null }

// Written without spaces between words, so their phrases join without one.
const UNSPACED_LANGUAGES = new Set(["zh", "ja", "yue", "th"])
// For a phrase whose language went unnamed: Han, kana and Thai.
export const UNSPACED_SCRIPT =
  /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}]/u
// Punctuation such as 。 or 「 belongs to no script, so the join reads the
// letter nearest it.
const LETTER = /\p{L}/u

function letterAt(text: string, end: "first" | "last"): string {
  const chars = [...text]
  const letter = (char: string) => LETTER.test(char)
  return (end === "first" ? chars.find(letter) : chars.findLast(letter)) ?? ""
}

function unspaced(phrase: TranscribedPhrase, edge: string): boolean {
  if (phrase.language !== null) {
    return UNSPACED_LANGUAGES.has(phrase.language.split("-")[0].toLowerCase())
  }
  return UNSPACED_SCRIPT.test(edge)
}

/**
 * Every phrase so far as one text: a space between phrases, none between two
 * in zh, ja, yue or th. assistant-ui would put a space between its finals.
 */
export function joinPhrases(phrases: readonly TranscribedPhrase[]): string {
  let joined = ""
  let previous: TranscribedPhrase | null = null
  for (const phrase of phrases) {
    const text = phrase.text.trim()
    if (!text) continue
    if (previous !== null) {
      const glued =
        unspaced(previous, letterAt(previous.text, "last")) &&
        unspaced(phrase, letterAt(text, "first"))
      if (!glued) joined += " "
    }
    joined += text
    previous = { ...phrase, text }
  }
  return joined
}
