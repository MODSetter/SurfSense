import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { compiledDictionary, switchTo } from "./compiled-dict.fixture.mjs"
import { copyEspeakData, trimEspeakData } from "./data.mjs"
import { KEPT_DICTIONARIES } from "./dictionaries.mjs"

/** An espeak-ng-data folder as the wheel carries it: shared files, every kept dictionary, and Chinese. */
function wheelData(root, dictionaries = {}) {
  const from = join(root, "espeak-ng-data")
  mkdirSync(join(from, "lang", "roa"), { recursive: true })
  mkdirSync(join(from, "voices", "!v"), { recursive: true })
  for (const file of ["phondata", "phondata-manifest", "phonindex", "phontab", "intonations"]) {
    writeFileSync(join(from, file), file)
  }
  writeFileSync(join(from, "lang", "roa", "it"), "name Italian")
  writeFileSync(join(from, "voices", "!v", "m1"), "variant")
  for (const language of [...KEPT_DICTIONARIES, "cmn"]) {
    writeFileSync(join(from, `${language}_dict`), dictionaries[language] ?? compiledDictionary())
  }
  return from
}

function inScratch(run) {
  const root = mkdtempSync(join(tmpdir(), "espeak-data-"))
  try {
    return run(root)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

test("stages the shared files and the reachable dictionaries, not Chinese's", () => {
  inScratch((root) => {
    const to = join(root, "staged")

    copyEspeakData(wheelData(root), to)

    const files = readdirSync(to)
    for (const language of KEPT_DICTIONARIES) assert.ok(files.includes(`${language}_dict`), language)
    assert.ok(!files.includes("cmn_dict"))
    for (const file of ["phondata", "phondata-manifest", "phonindex", "phontab", "intonations"]) {
      assert.ok(files.includes(file), file)
    }
    assert.ok(existsSync(join(to, "lang", "roa", "it")))
    assert.ok(existsSync(join(to, "voices", "!v", "m1")))
  })
})

test("fails when a staged dictionary sends words to one left out", () => {
  inScratch((root) => {
    const from = wheelData(root, { it: compiledDictionary({ words: [["nihao", switchTo("cmn")]] }) })

    assert.throws(() => copyEspeakData(from, join(root, "staged")), /it_dict switches to cmn/)
  })
})

test("fails when the wheel lacks a dictionary a voice needs", () => {
  inScratch((root) => {
    const from = wheelData(root)
    rmSync(join(from, "te_dict"))

    assert.throws(() => copyEspeakData(from, join(root, "staged")), /no te_dict/)
  })
})

test("trims, in place, data staged before the trimming", () => {
  // A stage kept as current would otherwise ship all 114 dictionaries.
  inScratch((root) => {
    const data = wheelData(root)

    assert.deepEqual(trimEspeakData(data), ["cmn_dict"])

    const files = readdirSync(data)
    assert.ok(!files.includes("cmn_dict"))
    for (const language of KEPT_DICTIONARIES) assert.ok(files.includes(`${language}_dict`), language)
    assert.ok(files.includes("phondata"))
    assert.ok(existsSync(join(data, "voices", "!v", "m1")))
    assert.deepEqual(trimEspeakData(data), [])
  })
})

test("trimming in place refuses, before removing anything, when a kept dictionary sends words to one left out", () => {
  inScratch((root) => {
    const data = wheelData(root, { pt: compiledDictionary({ words: [["nihao", switchTo("cmn")]] }) })

    assert.throws(() => trimEspeakData(data), /pt_dict switches to cmn/)
    assert.ok(existsSync(join(data, "cmn_dict")), "left as it was")
  })
})
