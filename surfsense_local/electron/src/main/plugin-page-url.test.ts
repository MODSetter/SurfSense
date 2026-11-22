import assert from "node:assert/strict"
import test from "node:test"

import { pluginPageUrl } from "./plugin-page-url.ts"

const API = "http://127.0.0.1:8000"

/** The local API as the main process reads it: the registry, as Settings lists it. */
function api(registry: unknown): typeof fetch {
  return (async (input: string | URL | Request) => {
    const url = String(input)
    if (url === `${API}/plugins/registry`) return Response.json(registry)
    return new Response(null, { status: 404 })
  }) as typeof fetch
}

const DEEPWIKI = {
  id: "deepwiki",
  homepage: "https://deepwiki.com",
  privacy_policy: "https://cognition.com/legal/privacy-policy",
}

test("opens a listed plugin's homepage and privacy policy, found by its id", async () => {
  const listed = api({ third_party_off: false, plugins: [DEEPWIKI] })

  assert.equal(
    await pluginPageUrl(API, "deepwiki", "homepage", listed),
    "https://deepwiki.com/"
  )
  assert.equal(
    await pluginPageUrl(API, "deepwiki", "privacy_policy", listed),
    "https://cognition.com/legal/privacy-policy"
  )
})

test("opens nothing for an unlisted id, an unknown page, or a page not on https", async () => {
  const listed = api({
    third_party_off: false,
    plugins: [{ ...DEEPWIKI, homepage: "http://deepwiki.com" }],
  })

  assert.equal(await pluginPageUrl(API, "nope", "homepage", listed), null)
  assert.equal(await pluginPageUrl(API, "deepwiki", "homepage", listed), null)
  assert.equal(
    await pluginPageUrl(API, "deepwiki", "url" as "homepage", listed),
    null
  )
})

test("opens nothing while third-party plugins are off or the API is down", async () => {
  assert.equal(
    await pluginPageUrl(
      API,
      "deepwiki",
      "homepage",
      api({ third_party_off: true, plugins: [] })
    ),
    null
  )
  const down = (async () => {
    throw new TypeError("fetch failed")
  }) as typeof fetch
  assert.equal(await pluginPageUrl(API, "deepwiki", "homepage", down), null)
})
