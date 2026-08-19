import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const dir = dirname(fileURLToPath(import.meta.url));

test("free model page does not SSR the chat shell", () => {
	const page = readFileSync(join(dir, "../../app/(home)/free/[model_slug]/page.tsx"), "utf8");
	assert.match(page, /FreeChatClient/);
	assert.doesNotMatch(page, /FreeChatPage|FreeLayoutDataProvider/);
	const client = readFileSync(join(dir, "free-chat-client.tsx"), "utf8");
	assert.match(client, /ssr:\s*false/);
});
