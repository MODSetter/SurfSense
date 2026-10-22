// The eSpeak-ng dictionaries the curated voices can reach. eSpeak loads one only
// for the voice's language or when a word switches language, so the other 93 of
// its 114 never load and do not ship (7 MB). Everything else ships whole.

// What the lists below were worked out from, and when: another eSpeak can move a
// script or a switch, and another audio.cpp or curated family can phonemise
// another language through eSpeak. A test fails until they are checked again.
export const DICTIONARIES_FOR = {
  espeak: "1.52.0",
  audiocpp: "v0.8.2",
  families: ["kokoro_tts", "supertonic", "kitten_tts", "nemotron_asr", "canary_asr"],
  on: "2026-10-21",
}

// Kokoro's eSpeak voices en-us, en, es, fr, hi, it and pt-br (g2p_multilingual.cpp)
// and Kitten's en-us. Kokoro's Chinese and Japanese, Supertonic and the speech
// recognisers do not phonemise through eSpeak.
const VOICES = ["en", "es", "fr", "hi", "it", "pt"]

// A word in one of these scripts switches to its language from any voice
// (alphabets[] in tr_languages.c). Without te_dict, Telugu crashed the server.
const SCRIPTS = ["el", "hy", "hi", "bn", "pa", "gu", "ta", "te", "kn", "ml", "si", "ka", "ko"]

// Where the dictionaries above send words: it_list's Cyrillic letters and Georgian's
// Cyrillic to ru, it_list's volkswagen and pt_list's ß to de, de_rules' Polish letters
// to pl. Staging checks these against the dictionaries themselves (switches.mjs).
const SWITCHED_TO = ["ru", "de", "pl"]

export const KEPT_DICTIONARIES = [...new Set([...VOICES, ...SCRIPTS, ...SWITCHED_TO])].sort()

const DICTIONARY = /^([a-z]+)_dict$/

/** Whether a path inside espeak-ng-data ships. */
export function shipsEspeakFile(relative) {
  const dictionary = DICTIONARY.exec(relative.split(/[\/]/)[0])
  return !dictionary || KEPT_DICTIONARIES.includes(dictionary[1])
}
