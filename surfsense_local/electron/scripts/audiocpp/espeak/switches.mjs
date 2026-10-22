// The languages a compiled eSpeak-ng dictionary sends words to (`_^_XX` in its
// sources), so staging fails rather than ship a dictionary whose target is
// missing: eSpeak then half-builds the translator and can crash.
import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

// 1.52.0's layout: N_HASH_DICT, then the rules' offset, then the word list's
// hash chains, each ending in a zero byte. phonSWITCH precedes the language name.
const HASH_CHAINS = 1024
const PHON_SWITCH = 0x15
const NAME = /^[a-z0-9-]*/
// compiledict drops the name of eSpeak's default voice.
const DEFAULT = "en"

// Each rule is its match and contexts, RULE_PHONEMES, its phonemes, then NUL; one
// sharing the previous rule's phonemes has none. A context's @ is phonSWITCH's
// byte, so only phonemes are read. These codes' operands can equal RULE_PHONEMES:
// RULE_CONDITION's number, RULE_LINENUM's two bytes, RULE_DOLLAR's ($list is 3).
const RULE_PHONEMES = 0x03
const OPERANDS = new Map([
  [0x05, 1],
  [0x09, 2],
  [0x1c, 1],
])

/** The language each phonSWITCH in `bytes` from `start` to `end` names. */
function switchesIn(bytes, start, end, found) {
  for (let i = start; i < end; i++) {
    if (bytes[i] !== PHON_SWITCH) continue
    found.add(NAME.exec(bytes.toString("latin1", i + 1, Math.min(i + 17, end)))[0] || DEFAULT)
  }
}

/** Where the phonemes of the NUL-ended rule at `start` begin, or -1 if it has none. */
function phonemesOf(bytes, start, end) {
  for (let i = start; i < end; i += 1 + (OPERANDS.get(bytes[i]) ?? 0)) {
    if (bytes[i] === RULE_PHONEMES) return i + 1
  }
  return -1
}

/** Each language `bytes`, a `*_dict` file, can switch a word to, sorted. */
export function dictionarySwitches(bytes) {
  const rules = bytes.length >= 8 ? bytes.readInt32LE(4) : -1
  if (bytes.length < 8 || bytes.readInt32LE(0) !== HASH_CHAINS || rules <= 8 || rules > bytes.length) {
    throw new Error("not a compiled eSpeak-ng dictionary")
  }
  const found = new Set()
  let p = 8
  for (let chain = 0; chain < HASH_CHAINS; chain++) {
    while (p < rules && bytes[p] !== 0) {
      const next = p + bytes[p]
      const noPhonemes = bytes[p + 1] & 0x80
      if (!noPhonemes) {
        const start = p + 2 + (bytes[p + 1] & 0x3f)
        switchesIn(bytes, start, bytes.indexOf(0, start), found)
      }
      p = next
    }
    p++
  }
  if (p !== rules) throw new Error("not a compiled eSpeak-ng dictionary: its word list does not end at its rules")
  for (let start = rules; start < bytes.length; ) {
    const nul = bytes.indexOf(0, start)
    const end = nul < 0 ? bytes.length : nul
    const phonemes = phonemesOf(bytes, start, end)
    if (phonemes >= 0) switchesIn(bytes, phonemes, end, found)
    start = end + 1
  }
  return [...found].sort()
}

/**
 * Each `*_dict` in `data` that switches to a language whose dictionary is not
 * there; with `ships`, as if only the files it accepts were there.
 */
export function unkeptSwitches(data, ships = () => true) {
  const present = readdirSync(data)
    .filter((file) => file.endsWith("_dict") && ships(file))
    .sort()
  const languages = new Set(present.map((file) => file.slice(0, -"_dict".length)))
  return present.flatMap((file) => {
    const from = file.slice(0, -"_dict".length)
    return dictionarySwitches(readFileSync(join(data, file)))
      .filter((to) => !languages.has(to))
      .map((to) => ({ from, to }))
  })
}
