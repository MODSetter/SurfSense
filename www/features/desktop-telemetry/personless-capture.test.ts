import assert from "node:assert/strict";
import { test } from "node:test";
import { gunzipSync } from "node:zlib";

// Run with: pnpm exec tsx --test features/desktop-telemetry/personless-capture.test.ts

import { createPersonlessCapture } from "./personless-capture";

type Sent = { url: string; body: { batch?: Array<Record<string, unknown>> } };

function postHogDouble() {
	const sent: Sent[] = [];
	const fetch = async (
		url: string,
		options: { body?: string | Blob; headers?: Record<string, string> }
	) => {
		let raw: Buffer;
		if (typeof options.body === "string") raw = Buffer.from(options.body);
		else raw = Buffer.from(await (options.body as Blob).arrayBuffer());
		const gzipped = options.headers?.["Content-Encoding"] === "gzip";
		sent.push({ url, body: JSON.parse((gzipped ? gunzipSync(raw) : raw).toString("utf8")) });
		return {
			status: 200,
			text: async () => "{}",
			json: async () => ({}),
			headers: { get: () => null },
		};
	};
	return {
		sent,
		fetch: fetch as unknown as Parameters<typeof createPersonlessCapture>[0]["fetch"],
	};
}

const EVENT = {
	event: "desktop_update_check",
	properties: {
		file: "stable.yml",
		app_version: "2.2.4",
		platform: "linux-x64",
		os: "linux",
		country: "FR",
	},
};

test("with no key nothing is sent", async () => {
	const { sent, fetch } = postHogDouble();
	await createPersonlessCapture({ apiKey: undefined, host: undefined, fetch })(EVENT);
	await createPersonlessCapture({ apiKey: "", host: "https://ph.example", fetch })(EVENT);
	assert.equal(sent.length, 0);
});

test("an event is sent before the capture resolves, personless and without GeoIP", async () => {
	const { sent, fetch } = postHogDouble();
	await createPersonlessCapture({ apiKey: "phc_test", host: "https://ph.example", fetch })(EVENT);

	assert.equal(sent.length, 1);
	assert.ok(sent[0].url.startsWith("https://ph.example/"), sent[0].url);
	const [event] = sent[0].body.batch ?? [];
	const properties = event.properties as Record<string, unknown>;
	assert.equal(event.event, "desktop_update_check");
	for (const [key, value] of Object.entries(EVENT.properties)) {
		assert.equal(properties[key], value, key);
	}
	assert.equal(properties.$process_person_profile, false);
	assert.equal(properties.$geoip_disable, true);
	assert.equal("$ip" in properties, false);
	assert.equal("ip" in event, false);
});

test("no two events share a distinct id, so nothing can be joined across them", async () => {
	const { sent, fetch } = postHogDouble();
	const capture = createPersonlessCapture({
		apiKey: "phc_test",
		host: "https://ph.example",
		fetch,
	});
	await capture(EVENT);
	await capture(EVENT);
	const ids = sent.map((request) => request.body.batch?.[0].distinct_id);
	assert.equal(ids.length, 2);
	assert.notEqual(ids[0], ids[1]);
});
