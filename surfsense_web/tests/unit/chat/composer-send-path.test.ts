import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

/**
 * ``ComposerPrimitive.Root`` renders a ``<form>``, so a ``type="submit"``
 * button inside it fires ``send()`` twice for one click: once from its own
 * onClick, once from the form's onSubmit. The second send raced the first,
 * aborted its request, and posted the message after the mention chips had
 * already been consumed and cleared — the "@mention silently dropped" bug.
 */
const source = readFileSync(
	new URL("../../../components/assistant-ui/thread.tsx", import.meta.url),
	"utf8"
);

test("no submit-typed button lives inside the composer form", () => {
	assert.ok(
		!source.includes('type="submit"'),
		'thread.tsx must not render type="submit" inside ComposerPrimitive.Root'
	);
});

test("the send button and the Enter key share one submit handler", () => {
	assert.ok(
		source.includes("onSend={handleSubmit}") && source.includes("onSubmit={handleSubmit}"),
		"send button and editor Enter must both call handleSubmit"
	);
});
