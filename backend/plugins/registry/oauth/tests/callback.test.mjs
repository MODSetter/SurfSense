// The callback page's inline script, run as a browser would run it, against the state contract.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const page = readFileSync(new URL("../callback.html", import.meta.url), "utf8");
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const NONCE = "Zq3_-xY7kLm9PqRs2TuVw";

function opened(search) {
  const replaced = [];
  const message = { hidden: true };
  const context = {
    URLSearchParams,
    location: { search, replace: (url) => replaced.push(url) },
    document: { getElementById: (id) => (id === "invalid" ? message : null) },
  };
  vm.runInNewContext(script, context);
  return { replaced, messageShown: !message.hidden };
}

test("a valid state forwards the whole query to the app's loopback port", () => {
  const search = `?code=abc&state=43123.${NONCE}&iss=https%3A%2F%2Fauth.example`;
  const { replaced, messageShown } = opened(search);
  assert.deepEqual(replaced, [`http://127.0.0.1:43123/plugins/oauth/callback${search}`]);
  assert.equal(messageShown, false);
});

test("an error from the provider is forwarded too", () => {
  const search = `?error=access_denied&error_description=No&state=1024.${NONCE}`;
  assert.deepEqual(opened(search).replaced, [
    `http://127.0.0.1:1024/plugins/oauth/callback${search}`,
  ]);
});

for (const [why, search] of [
  ["no query", ""],
  ["no state", "?code=abc"],
  ["empty state", "?code=abc&state="],
  ["no nonce", "?state=43123"],
  ["empty nonce", "?state=43123."],
  ["short nonce", "?state=43123.abc"],
  ["nonce with other characters", `?state=43123.${NONCE}%2F..`],
  ["port below 1024", `?state=1023.${NONCE}`],
  ["port above 65535", `?state=65536.${NONCE}`],
  ["port with a leading zero", `?state=01024.${NONCE}`],
  ["port that is not digits", `?state=8o80.${NONCE}`],
  ["port with a host in it", `?state=evil.example:80.${NONCE}`],
  ["two states", `?state=43123.${NONCE}&state=43124.${NONCE}`],
]) {
  test(`${why} shows the message and goes nowhere`, () => {
    const { replaced, messageShown } = opened(search);
    assert.deepEqual(replaced, []);
    assert.equal(messageShown, true);
  });
}

test("the page loads nothing from anywhere and allows only its own inline code", () => {
  const policy = page.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];
  const style = page.match(/<style>([\s\S]*?)<\/style>/)[1];
  const hash = (text) => `'sha256-${createHash("sha256").update(text).digest("base64")}'`;
  assert.match(policy, /default-src 'none'/);
  assert.ok(policy.includes(`script-src ${hash(script)}`), "script hash is stale");
  assert.ok(policy.includes(`style-src ${hash(style)}`), "style hash is stale");
  assert.doesNotMatch(page, /<script[^>]+src=/);
  assert.doesNotMatch(page, /<link /);
});
