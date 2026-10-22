import assert from "node:assert/strict"
import test from "node:test"

import { ESPEAK_VERSION, FAMILIES, TAG } from "../pins.mjs"
import { DICTIONARIES_FOR, KEPT_DICTIONARIES, shipsEspeakFile } from "./dictionaries.mjs"

const shipped = (language) => shipsEspeakFile(`${language}_dict`)

test("ships the dictionary of every eSpeak voice the curated voices select", () => {
  // audio.cpp v0.8.2's Kokoro: en-us, en, es, fr, hi, it, pt-br; Kitten: en-us.
  for (const language of ["en", "es", "fr", "hi", "it", "pt"]) assert.ok(shipped(language), language)
})

test("ships every language a word's script switches to, from any voice", () => {
  // alphabets[] in eSpeak 1.52.0's tr_languages.c; without te_dict a Telugu word crashed the server.
  for (const language of ["el", "hy", "hi", "bn", "pa", "gu", "ta", "te", "kn", "ml", "si", "ka", "ko"]) {
    assert.ok(shipped(language), language)
  }
})

test("ships the languages shipped dictionaries send words to", () => {
  // it_list: Cyrillic letters and volkswagen; pt_list: ß and feuerbach; de_rules: Polish letters.
  for (const language of ["ru", "de", "pl"]) assert.ok(shipped(language), language)
})

test("drops the dictionaries no voice can reach, Chinese among them", () => {
  // Kokoro's Chinese voices phonemise with Jieba and pinyin, not eSpeak.
  for (const language of ["cmn", "yue", "ja", "ar", "tr", "uk", "vi"]) assert.ok(!shipped(language), language)
  assert.equal(KEPT_DICTIONARIES.length, 21)
})

test("ships everything that is not a dictionary", () => {
  for (const file of ["phondata", "phondata-manifest", "phonindex", "phontab", "intonations", "lang/roa/it", "voices/!v/m1"]) {
    assert.ok(shipsEspeakFile(file), file)
  }
  assert.ok(shipsEspeakFile(""), "the folder itself")
})

test("was worked out for the eSpeak-ng, audio.cpp and curated families the pins stage", () => {
  // Another eSpeak can move a script or a switch; another audio.cpp or family can
  // phonemise another language through eSpeak. Check the lists again, then these.
  assert.equal(DICTIONARIES_FOR.espeak, ESPEAK_VERSION)
  assert.equal(DICTIONARIES_FOR.audiocpp, TAG)
  assert.deepEqual(DICTIONARIES_FOR.families, FAMILIES)
})

test("dates the list, for the notice the GPL asks of a modified copy", () => {
  assert.match(DICTIONARIES_FOR.on, /^\d{4}-\d{2}-\d{2}$/)
  assert.ok(!Number.isNaN(Date.parse(DICTIONARIES_FOR.on)), DICTIONARIES_FOR.on)
})
