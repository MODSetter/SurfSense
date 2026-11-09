import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import {
  compiledDictionary,
  DOLLAR_LIST,
  RULE_CONDITION,
  RULE_DOLLAR,
  RULE_POST,
  RULE_SYLLABLE,
  switchTo,
} from "./compiled-dict.fixture.mjs"
import { dictionarySwitches, unkeptSwitches } from "./switches.mjs"

const PLAIN = Buffer.from([0x30, 0x41, 0x52])

test("a dictionary that sends no word elsewhere switches nowhere", () => {
  const dict = compiledDictionary({ words: [["casa", PLAIN]], rules: [["c", PLAIN]] })
  assert.deepEqual(dictionarySwitches(dict), [])
})

test("finds the languages its words switch to, as it_list's volkswagen does", () => {
  const dict = compiledDictionary({
    words: [
      ["volkswagen", switchTo("de")],
      ["а", switchTo("ru")],
      ["casa", PLAIN],
    ],
  })
  assert.deepEqual(dictionarySwitches(dict), ["de", "ru"])
})

test("finds the languages its rules switch to, as de_rules sends ł to pl", () => {
  const dict = compiledDictionary({ rules: [["ł", switchTo("pl")], ["a", PLAIN]] })
  assert.deepEqual(dictionarySwitches(dict), ["pl"])
})

test("a rule's @ context, the same byte as a switch, switches nowhere", () => {
  // af_rules: rules sharing the previous rule's phonemes end in their context, as (@n does.
  const dict = compiledDictionary({
    rules: [
      ["b", PLAIN],
      [Buffer.from([0x61, RULE_POST, RULE_SYLLABLE, 0x6e]), null],
      [Buffer.from([0x61, RULE_POST, RULE_SYLLABLE]), null],
    ],
  })
  assert.deepEqual(dictionarySwitches(dict), [])
})

test("an operand with RULE_PHONEMES' byte does not start a rule's phonemes", () => {
  const dict = compiledDictionary({
    rules: [
      // $list's operand, then @n in the context, then plain phonemes.
      [Buffer.from([0x61, RULE_POST, RULE_DOLLAR, DOLLAR_LIST, RULE_SYLLABLE, 0x6e]), PLAIN],
      // Condition 3, then a real switch.
      [Buffer.from([0x62, RULE_CONDITION, 0x03]), switchTo("pl")],
    ],
  })
  assert.deepEqual(dictionarySwitches(dict), ["pl"])
})

test("a switch with no name goes to eSpeak's default, English", () => {
  const dict = compiledDictionary({ words: [["bordeaux", switchTo("")]] })
  assert.deepEqual(dictionarySwitches(dict), ["en"])
})

test("a switch ending in more phonemes still names its language", () => {
  const dict = compiledDictionary({
    words: [["chapeau", Buffer.concat([switchTo("fr"), Buffer.from("|"), PLAIN])]],
  })
  assert.deepEqual(dictionarySwitches(dict), ["fr"])
})

test("refuses a file that is not a 1.52.0 compiled dictionary", () => {
  assert.throws(() => dictionarySwitches(Buffer.from("not a dictionary at all")), /not a compiled eSpeak-ng dictionary/)
})

test("names each staged dictionary that switches to one not staged", () => {
  const data = mkdtempSync(join(tmpdir(), "espeak-switches-"))
  try {
    writeFileSync(join(data, "it_dict"), compiledDictionary({ words: [["volkswagen", switchTo("de")]] }))
    writeFileSync(join(data, "pt_dict"), compiledDictionary({ words: [["ß", switchTo("de")]] }))
    writeFileSync(join(data, "ka_dict"), compiledDictionary({ words: [["x", switchTo("")]] }))
    writeFileSync(join(data, "en_dict"), compiledDictionary())
    writeFileSync(join(data, "phontab"), "")

    assert.deepEqual(unkeptSwitches(data), [
      { from: "it", to: "de" },
      { from: "pt", to: "de" },
    ])
    writeFileSync(join(data, "de_dict"), compiledDictionary())
    assert.deepEqual(unkeptSwitches(data), [])
    assert.deepEqual(unkeptSwitches(data, (file) => file !== "de_dict" && file !== "pt_dict"), [{ from: "it", to: "de" }])
  } finally {
    rmSync(data, { recursive: true, force: true })
  }
})
