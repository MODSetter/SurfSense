import assert from "node:assert/strict"
import test from "node:test"

import { REVIEWED_TEXTS } from "./reviewed-texts.mjs"

test("each reviewed text names its source, and its copyright line is the recorded holder's", () => {
  for (const reviewed of REVIEWED_TEXTS) {
    assert.ok(reviewed.source?.trim(), `${reviewed.name} has no source`)
    assert.ok(reviewed.copyright?.trim(), `${reviewed.name} has no copyright holder`)
    assert.match(reviewed.text, new RegExp(`^Copyright \\(c\\) ${reviewed.copyright}$`, "m"))
  }
})
