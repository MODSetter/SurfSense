import assert from "node:assert/strict"
import test from "node:test"

import { allowedExternalUrl, confirmedExternalUrl } from "./external-url.ts"

test("opens the SurfSense site", () => {
  assert.equal(
    allowedExternalUrl("https://www.surfsense.com/docs"),
    "https://www.surfsense.com/docs"
  )
  assert.equal(
    allowedExternalUrl("https://surfsense.com/downloads"),
    "https://surfsense.com/downloads"
  )
})

test("opens the project's GitHub repository and nothing else on GitHub", () => {
  assert.equal(
    allowedExternalUrl(
      "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2"
    ),
    "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2"
  )
  assert.equal(
    allowedExternalUrl("https://github.com/MODSetter/SurfSense"),
    "https://github.com/MODSetter/SurfSense"
  )
  assert.equal(allowedExternalUrl("https://github.com/MODSetter"), null)
  assert.equal(
    allowedExternalUrl("https://github.com/MODSetter/SurfSense-evil"),
    null
  )
  assert.equal(allowedExternalUrl("https://github.com/someone/else"), null)
})

test("opens the community Discord invite only", () => {
  assert.equal(
    allowedExternalUrl("https://discord.gg/ejRNvftDp9"),
    "https://discord.gg/ejRNvftDp9"
  )
  assert.equal(allowedExternalUrl("https://discord.gg/other"), null)
})

test("opens OpenRouter's two-segment pages, as a model's is, and no other shape", () => {
  assert.equal(
    allowedExternalUrl("https://openrouter.ai/hexgrad/kokoro-82m"),
    "https://openrouter.ai/hexgrad/kokoro-82m"
  )
  assert.equal(
    allowedExternalUrl("https://openrouter.ai/bytedance-seed/seed-audio-1-0"),
    "https://openrouter.ai/bytedance-seed/seed-audio-1-0"
  )
  assert.equal(allowedExternalUrl("https://openrouter.ai/"), null)
  assert.equal(allowedExternalUrl("https://openrouter.ai/a/b/c"), null)
  assert.equal(allowedExternalUrl("https://openrouter.ai/a/b?x=1"), null)
  assert.equal(allowedExternalUrl("https://evil.openrouter.ai/a/b"), null)
})

test("refuses other schemes and hosts", () => {
  assert.equal(allowedExternalUrl("http://surfsense.com"), null)
  assert.equal(allowedExternalUrl("file:///etc/passwd"), null)
  assert.equal(allowedExternalUrl("https://evil.surfsense.com.example"), null)
  assert.equal(allowedExternalUrl("not a url"), null)
})

test("opens OpenAI's sign-in page only when it redirects back to this machine", () => {
  const authorize = "https://auth.openai.com/api/accounts/authorize"
  const back = encodeURIComponent("http://127.0.0.1:53111/callback")
  const signIn = `${authorize}?client_id=dynamic_agent_client&redirect_uri=${back}`
  assert.equal(allowedExternalUrl(signIn), signIn)
  assert.equal(
    allowedExternalUrl(
      `${authorize}?redirect_uri=${encodeURIComponent("https://evil.example/callback")}`
    ),
    null
  )
  assert.equal(
    allowedExternalUrl(
      `${authorize}?redirect_uri=${encodeURIComponent("http://127.0.0.1:53111/other")}`
    ),
    null
  )
  assert.equal(allowedExternalUrl(`${authorize}`), null)
  assert.equal(allowedExternalUrl("https://auth.openai.com/log-in"), null)
})

test("opens a plugin's sign-in page only when it comes back to SurfSense with PKCE", () => {
  const signIn = (redirect: string, extra: Record<string, string> = {}) =>
    `https://auth.notes.example/authorize?${new URLSearchParams({
      response_type: "code",
      client_id: "client-1",
      redirect_uri: redirect,
      state: "53111.Abc_def-0123456789xyz",
      code_challenge: "x".repeat(43),
      code_challenge_method: "S256",
      ...extra,
    })}`
  const hosted = signIn("https://plugins.surfsense.com/oauth/callback")
  const loopback = signIn("http://127.0.0.1:53111/plugins/oauth/callback")
  assert.equal(allowedExternalUrl(hosted), hosted)
  assert.equal(allowedExternalUrl(loopback), loopback)

  assert.equal(allowedExternalUrl(signIn("https://evil.example/oauth/callback")), null)
  assert.equal(
    allowedExternalUrl(signIn("http://127.0.0.1:53111/callback")),
    null
  )
  assert.equal(
    allowedExternalUrl(
      signIn("https://plugins.surfsense.com/oauth/callback", { state: "nonce" })
    ),
    null
  )
  assert.equal(
    allowedExternalUrl(
      signIn("https://plugins.surfsense.com/oauth/callback", {
        code_challenge_method: "plain",
      })
    ),
    null
  )
  assert.equal(
    allowedExternalUrl(
      hosted.replace("https://auth.notes.example", "http://auth.notes.example")
    ),
    null
  )
})

test("a link the user confirmed opens on any https host, and nothing else", () => {
  assert.equal(
    confirmedExternalUrl("https://app.notion.com/p/329aedcce14281f6"),
    "https://app.notion.com/p/329aedcce14281f6"
  )
  assert.equal(confirmedExternalUrl("http://app.notion.com/p/1"), null)
  assert.equal(confirmedExternalUrl("file:///etc/passwd"), null)
  assert.equal(confirmedExternalUrl("javascript:alert(1)"), null)
  assert.equal(confirmedExternalUrl("https://me:pw@app.notion.com/"), null) // pragma: allowlist secret
  assert.equal(confirmedExternalUrl("not a url"), null)
})

test("opens Claude Code's install guide and nothing else on its docs site", () => {
  assert.equal(
    allowedExternalUrl("https://code.claude.com/docs/en/setup"),
    "https://code.claude.com/docs/en/setup"
  )
  assert.equal(allowedExternalUrl("https://code.claude.com/docs/en/overview"), null)
  assert.equal(allowedExternalUrl("https://code.claude.com/docs/en/setup?x=1"), null)
  assert.equal(allowedExternalUrl("http://code.claude.com/docs/en/setup"), null)
  assert.equal(allowedExternalUrl("https://claude.ai/"), null)
})
