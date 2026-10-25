// electron-builder's afterSign hook: checks the opencode the app now carries,
// signed and on macOS notarized, before any installer is made, because a tag's
// build uploads each installer to the draft release as soon as it exists.
// macOS and Windows run it on every build; Linux signs nothing, so electron-builder
// skips it there with a warning, and release CI checks that copy after the build.
import { join } from "node:path"

import { checkStage } from "./check-stage.mjs"
import { opencodeEnabled } from "./enabled.mjs"

/** @param {import("electron-builder").AfterPackContext} context */
export default async function afterSign(context) {
  if (!opencodeEnabled()) return
  const folder = join(context.packager.getResourcesDir(context.appOutDir), "opencode")
  checkStage(folder)
  console.log(`opencode runs from ${folder} after signing`)
}
