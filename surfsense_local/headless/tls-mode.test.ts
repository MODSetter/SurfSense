import assert from "node:assert/strict"
import { test } from "node:test"

import { tlsMode } from "./tls-mode.ts"

test("with neither a domain nor TLS asked for, Caddy serves plain HTTP", () => {
  assert.deepEqual(tlsMode({}), { caddyfile: "Caddyfile", env: {} })
})

test("a public domain gets its own certificate, and the domain is all Caddy needs", () => {
  assert.deepEqual(tlsMode({ SURFSENSE_DOMAIN: "surfsense.example.com" }), {
    caddyfile: "Caddyfile.domain",
    env: { SURFSENSE_DOMAIN: "surfsense.example.com" },
  })
})

test("on a LAN, Caddy's own certificates cover each allowed host, and HTTP redirects to the published port", () => {
  const mode = tlsMode({
    SURFSENSE_TLS: "internal",
    SURFSENSE_ALLOWED_HOSTS: "surfsense.lan, 192.168.1.20",
    SURFSENSE_HTTPS_PORT: "4943",
  })
  assert.deepEqual(mode, {
    caddyfile: "Caddyfile.lan",
    env: {
      SURFSENSE_TLS_SITES: "https://surfsense.lan, https://192.168.1.20",
      SURFSENSE_HTTPS_PORT: "4943",
    },
  })
})

test("LAN HTTPS without allowed hosts is refused: Caddy cannot know which names to certify", () => {
  assert.throws(() => tlsMode({ SURFSENSE_TLS: "internal" }), /SURFSENSE_ALLOWED_HOSTS/)
})

test("an unknown TLS mode is refused rather than ignored", () => {
  assert.throws(() => tlsMode({ SURFSENSE_TLS: "acme" }), /SURFSENSE_TLS/)
})

test("a domain wins over LAN TLS: one certificate authority per instance", () => {
  const mode = tlsMode({ SURFSENSE_DOMAIN: "surfsense.example.com", SURFSENSE_TLS: "internal" })
  assert.equal(mode.caddyfile, "Caddyfile.domain")
})
