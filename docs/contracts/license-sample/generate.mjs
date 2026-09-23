#!/usr/bin/env node
// Regenerate the contract-1 fixtures with a TEST Ed25519 key. Node built-ins only.
//
//     node generate.mjs
//
// The key comes from a fixed seed and Ed25519 signing is deterministic, so every
// run writes byte-identical files. The script verifies each file the way the app
// must (raw hex public key, "license/" prefix) and asserts a tampered payload
// fails, so it doubles as the contract's self-check. THIS KEY IS NOT THE
// PRODUCTION KEYGEN KEY; it exists so the verifier can be built before Keygen does.

import { createPrivateKey, createPublicKey, sign, verify } from "node:crypto";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

// Ed25519 private key = 32-byte seed wrapped in a fixed PKCS#8 DER prefix.
const SEED = Buffer.from("surfsense-contract-1-test-seed!!"); // exactly 32 bytes
const PKCS8_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");
const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

const privateKey = createPrivateKey({ key: Buffer.concat([PKCS8_PREFIX, SEED]), format: "der", type: "pkcs8" });
const rawPublic = createPublicKey(privateKey).export({ type: "spki", format: "der" }).subarray(-32);
const publicKeyHex = rawPublic.toString("hex"); // what Keygen's dashboard shows

// The app's side: rebuild a key object from the raw hex, as it will from the compiled-in constant.
const appPublicKey = createPublicKey({
  key: Buffer.concat([SPKI_PREFIX, Buffer.from(publicKeyHex, "hex")]),
  format: "der",
  type: "spki",
});

const ISSUED = "2026-09-10T00:00:00.000Z";
const POLICY = { trial: "5b1f7a9e-0000-4000-8000-000000000001", individual: "5b1f7a9e-0000-4000-8000-000000000002", team: "5b1f7a9e-0000-4000-8000-000000000003" };

function license({ id, key, plan, email, expiry, maxUsers = null }) {
  return {
    meta: { issued: ISSUED, expiry: null, ttl: null },
    data: {
      id,
      type: "licenses",
      attributes: {
        name: null,
        key,
        expiry,
        status: new Date(expiry) < new Date(ISSUED) ? "EXPIRED" : "ACTIVE",
        suspended: false,
        maxUsers,
        metadata: { plan, email },
        created: ISSUED,
        updated: ISSUED,
      },
      relationships: { policy: { data: { type: "policies", id: POLICY[plan] } } },
    },
  };
}

function certificate(payload) {
  const enc = Buffer.from(JSON.stringify(payload)).toString("base64");
  const sig = sign(null, Buffer.from(`license/${enc}`), privateKey).toString("base64");
  const body = Buffer.from(JSON.stringify({ enc, sig, alg: "base64+ed25519" })).toString("base64");
  const wrapped = body.match(/.{1,64}/g).join("\n");
  return `-----BEGIN LICENSE FILE-----\n${wrapped}\n-----END LICENSE FILE-----\n`;
}

// The consumer's steps 1-3 from 01-license-file.md, used here as the self-check.
function verifyCertificate(text) {
  const b64 = text.replace(/-----(BEGIN|END) LICENSE FILE-----/g, "").replace(/\s+/g, "");
  const { enc, sig, alg } = JSON.parse(Buffer.from(b64, "base64").toString());
  if (alg !== "base64+ed25519") throw new Error("unsupported_algorithm");
  if (!verify(null, Buffer.from(`license/${enc}`), appPublicKey, Buffer.from(sig, "base64"))) throw new Error("bad_signature");
  return JSON.parse(Buffer.from(enc, "base64").toString());
}

const fixtures = {
  "individual.lic": license({ id: "c0ffee00-0000-4000-8000-000000000101", key: "TEST-INDV-2026-0001", plan: "individual", email: "ada@example.com", expiry: "2027-09-10T00:00:00.000Z" }),
  "team.lic": license({ id: "c0ffee00-0000-4000-8000-000000000102", key: "TEST-TEAM-2026-0002", plan: "team", email: "ops@example.com", expiry: "2027-09-10T00:00:00.000Z", maxUsers: 12 }),
  "trial.lic": license({ id: "c0ffee00-0000-4000-8000-000000000103", key: "TEST-TRIL-2026-0003", plan: "trial", email: "try@example.com", expiry: "2026-09-24T00:00:00.000Z" }),
  "expired.lic": license({ id: "c0ffee00-0000-4000-8000-000000000104", key: "TEST-INDV-2025-0004", plan: "individual", email: "old@example.com", expiry: "2025-01-01T00:00:00.000Z" }),
};

writeFileSync(join(here, "public-key.hex"), publicKeyHex + "\n");
for (const [name, payload] of Object.entries(fixtures)) {
  const cert = certificate(payload);
  writeFileSync(join(here, name), cert);
  const back = verifyCertificate(cert);
  if (back.data.attributes.key !== payload.data.attributes.key) throw new Error(`${name}: round trip mismatch`);
  console.log(`ok ${name} plan=${back.data.attributes.metadata.plan} status=${back.data.attributes.status}`);
}

// Tamper check: flip one byte of enc and confirm the signature no longer verifies.
{
  const cert = certificate(fixtures["individual.lic"]);
  const b64 = cert.replace(/-----(BEGIN|END) LICENSE FILE-----/g, "").replace(/\s+/g, "");
  const outer = JSON.parse(Buffer.from(b64, "base64").toString());
  const payload = JSON.parse(Buffer.from(outer.enc, "base64").toString());
  payload.data.attributes.expiry = "2099-01-01T00:00:00.000Z";
  outer.enc = Buffer.from(JSON.stringify(payload)).toString("base64");
  const forged = `-----BEGIN LICENSE FILE-----\n${Buffer.from(JSON.stringify(outer)).toString("base64")}\n-----END LICENSE FILE-----\n`;
  let failed = false;
  try { verifyCertificate(forged); } catch (e) { failed = e.message === "bad_signature"; }
  if (!failed) throw new Error("tampered file verified; the check is broken");
  console.log("ok tampered payload rejected with bad_signature");
}
console.log(`public key ${publicKeyHex}`);
