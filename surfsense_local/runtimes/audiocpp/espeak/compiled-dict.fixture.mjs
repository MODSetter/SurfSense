// Builds a compiled eSpeak-ng 1.52.0 `*_dict` in memory, for the trimming tests.
const HASH_CHAINS = 1024
export const PHON_SWITCH = 0x15
const RULE_PHONEMES = 0x03
const RULE_GROUP_START = 0x06
const RULE_GROUP_END = 0x07

// A rule's codes, as compiledict writes them between its match and its phonemes.
export const RULE_POST = 0x02
export const RULE_CONDITION = 0x05
export const RULE_SYLLABLE = 0x15
export const RULE_DOLLAR = 0x1c
export const DOLLAR_LIST = 0x03

/** A word-list entry: the word, then its phoneme bytes, as compiledict writes it. */
function entry(word, phonemes) {
  const text = Buffer.from(word, "utf8")
  const body = Buffer.concat([Buffer.from([text.length]), text, phonemes, Buffer.from([0])])
  return Buffer.concat([Buffer.from([body.length + 1]), body])
}

/** A switch to `language` (empty for eSpeak's default), as `_^_XX` compiles. */
export function switchTo(language) {
  return Buffer.concat([Buffer.from([PHON_SWITCH]), Buffer.from(language, "ascii")])
}

/** A rule: its match and contexts, then its phonemes, or none when it shares the previous rule's. */
function rule(match, phonemes) {
  const text = Buffer.isBuffer(match) ? match : Buffer.from(match, "utf8")
  const tail = phonemes === null ? [] : [Buffer.from([RULE_PHONEMES]), phonemes]
  return Buffer.concat([text, ...tail, Buffer.from([0])])
}

/**
 * `words`: [word, phoneme bytes] pairs for the list; `rules`: [match, phoneme bytes
 * or null] pairs, all in one rule group. A Buffer match carries context bytes.
 */
export function compiledDictionary({ words = [], rules = [] } = {}) {
  const chains = [Buffer.concat(words.map(([word, phonemes]) => entry(word, phonemes)))]
  const list = Buffer.concat([...chains, Buffer.alloc(HASH_CHAINS, 0)])
  const ruleBytes = Buffer.concat([
    Buffer.from([RULE_GROUP_START]),
    Buffer.from("a\0", "ascii"),
    ...rules.map(([match, phonemes]) => rule(match, phonemes)),
    Buffer.from([RULE_GROUP_END, 0]),
  ])
  const header = Buffer.alloc(8)
  header.writeInt32LE(HASH_CHAINS, 0)
  header.writeInt32LE(8 + list.length, 4)
  return Buffer.concat([header, list, ruleBytes])
}
