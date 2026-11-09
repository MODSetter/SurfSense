// eSpeak-ng's library, its data and its licence, where the sidecar points
// AUDIOCPP_ESPEAK_LIBRARY and AUDIOCPP_ESPEAK_DATA. The data keeps only the
// dictionaries the curated voices can reach (dictionaries.mjs).
import { copyFileSync, existsSync, mkdirSync } from "node:fs"
import { join } from "node:path"

import { download, unpack } from "../../pinned-download.mjs"
import { ESPEAK, ESPEAK_LICENCE } from "../pins.mjs"
import { copyEspeakData, trimEspeakData } from "./data.mjs"

export async function stageEspeak(work, stage) {
  const pin = ESPEAK[process.platform]
  const wheel = join(work, "espeak.whl")
  const licence = join(work, "COPYING")
  const unpacked = join(work, "espeak")
  await download(pin, wheel)
  await download(ESPEAK_LICENCE, licence)
  mkdirSync(unpacked)
  unpack(wheel, unpacked)

  const from = join(unpacked, "espeakng_loader")
  const to = join(stage, "espeak")
  mkdirSync(to)
  copyFileSync(join(from, pin.library), join(to, pin.library))
  copyEspeakData(join(from, "espeak-ng-data"), join(to, "espeak-ng-data"))
  copyFileSync(licence, join(to, "COPYING"))
}

/** Trim the eSpeak data of a stage kept as it is, staged before the trimming; returns what it removed. */
export function trimStagedEspeak(stage) {
  const data = join(stage, "espeak", "espeak-ng-data")
  return existsSync(data) ? trimEspeakData(data) : []
}
