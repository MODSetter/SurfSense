// eSpeak-ng's data as the app ships it: every file but the dictionaries no
// curated voice can reach, refused if a shipped one switches to a dropped one.
import { cpSync, existsSync, readdirSync, rmSync } from "node:fs"
import { join, relative } from "node:path"

import { KEPT_DICTIONARIES, shipsEspeakFile } from "./dictionaries.mjs"
import { unkeptSwitches } from "./switches.mjs"

function refuseMissing(data) {
  const absent = KEPT_DICTIONARIES.filter((language) => !existsSync(join(data, `${language}_dict`)))
  if (absent.length) {
    throw new Error(`eSpeak-ng's data has no ${absent.map((language) => `${language}_dict`).join(", ")}`)
  }
}

function refuseUnkeptSwitches(data, ships) {
  const gaps = unkeptSwitches(data, ships)
  if (gaps.length) {
    const list = gaps.map(({ from: source, to: target }) => `${source}_dict switches to ${target}`).join(", ")
    throw new Error(`${list}, which is not staged: add it to runtimes/audiocpp/espeak/dictionaries.mjs`)
  }
}

/** Copy the wheel's espeak-ng-data folder `from` to `to`, trimmed. */
export function copyEspeakData(from, to) {
  refuseMissing(from)
  cpSync(from, to, { recursive: true, filter: (path) => shipsEspeakFile(relative(from, path)) })
  refuseUnkeptSwitches(to)
}

/** Trim a staged espeak-ng-data folder in place; returns the files it removed. */
export function trimEspeakData(data) {
  refuseMissing(data)
  refuseUnkeptSwitches(data, shipsEspeakFile)
  const removed = readdirSync(data)
    .filter((file) => !shipsEspeakFile(file))
    .sort()
  for (const file of removed) rmSync(join(data, file), { recursive: true, force: true })
  return removed
}
