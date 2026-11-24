import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { designatedRequirement, REQUIREMENT_FILE, requirementProblem } from "./designated-requirement.mjs"

const REQUIREMENT = readFileSync(REQUIREMENT_FILE, "utf8")

/** `codesign -d -r-` on 2.4.0's app, as macOS prints an explicit requirement. */
const SHIPPED = `designated => anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */
`

test("the requirement accepts a Developer ID app from any team, so a future Apple team can update 2.4.0", () => {
  // No identifier: electron-builder stamps it on every nested helper and framework too.
  // No team: 2.4.0 cannot know the next one. The signed manifest vouches for the build.
  assert.equal(
    designatedRequirement(REQUIREMENT),
    "anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] and certificate leaf[field.1.2.840.113635.100.6.1.13]"
  )
  assert.doesNotMatch(REQUIREMENT, /identifier|subject\.OU/)
})

test("an app signed with it passes, codesign's notes aside", () => {
  assert.equal(requirementProblem(SHIPPED, REQUIREMENT), null)
})

test("an app signed with the default requirement, which names the team, fails", () => {
  const teamPinned = `designated => identifier "com.surfsense.app" and anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and certificate leaf[subject.OU] = ABCDE12345\n`

  assert.match(requirementProblem(teamPinned, REQUIREMENT) ?? "", /^the app's designated requirement is identifier/)
})

test("an app with only an implicit requirement fails", () => {
  const adHoc = '# designated => cdhash H"0123456789abcdef0123456789abcdef01234567"\n' // pragma: allowlist secret
  assert.equal(
    requirementProblem(adHoc, REQUIREMENT),
    "the app carries no explicit designated requirement"
  )
})

test("electron-builder signs the Mac app with that file", () => {
  const yml = readFileSync(new URL("../../electron-builder.yml", import.meta.url), "utf8").replace(/\r\n/g, "\n")
  const mac = yml.match(/^mac:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  assert.match(mac, /^  requirements: build\/designated-requirement\.txt$/m)
})
