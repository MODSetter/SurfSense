import assert from "node:assert/strict"
import test from "node:test"

import { USAGE_ENDPOINT, usageEndpoint } from "./usage-endpoint.ts"

test("a packaged app reports to usage.surfsense.com, whatever the environment says", () => {
  assert.equal(USAGE_ENDPOINT, "https://usage.surfsense.com/api/usage")
  assert.equal(
    usageEndpoint({
      packaged: true,
      env: { SURFSENSE_TELEMETRY_DEV_ENDPOINT: "http://localhost:3000/api/usage" },
    }),
    USAGE_ENDPOINT
  )
})

test("a development build reports only to a test endpoint it is given", () => {
  assert.equal(usageEndpoint({ packaged: false, env: {} }), null)
  assert.equal(
    usageEndpoint({ packaged: false, env: { SURFSENSE_TELEMETRY_DEV_ENDPOINT: " " } }),
    null
  )
  assert.equal(
    usageEndpoint({ packaged: false, env: { SURFSENSE_TELEMETRY_DEV_ENDPOINT: "file:///tmp/x" } }),
    null
  )
  assert.equal(
    usageEndpoint({
      packaged: false,
      env: { SURFSENSE_TELEMETRY_DEV_ENDPOINT: "http://localhost:3000/api/usage" },
    }),
    "http://localhost:3000/api/usage"
  )
})
