import assert from "node:assert/strict";
import { test } from "node:test";

// Run with: pnpm exec tsx --test features/desktop-telemetry/usage-report/usage-report.test.ts

import type { PersonlessEvent } from "../personless-capture";
import { receiveUsageReport } from "./receive-usage-report";

// The contract's own example as a 2.2.4 app sends it: a first report of the
// week, not the install's first, with no trigger.
const REPORT = {
	schema: 1,
	app_version: "2.2.4",
	platform: "win32-x64",
	os: "windows-11",
	ui_language: "en",
	install_week: "2026-W43",
	active: { first: false, week: true, month: false },
	hardware: null,
	week: {
		chat_turns: "10-49",
		agent_turns: "0",
		model_source: "local",
		sources: "10-99",
		studio_outputs: "1-4",
		plugin_calls: "0",
		onboarding: "first_answer",
	},
};

const FIRST_REPORT = {
	...REPORT,
	active: { first: true, week: true, month: true },
	hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11" },
};

// Revision 1.1: sent in the first week when setup reaches a new step.
const SETUP_REPORT = {
	...REPORT,
	trigger: "setup",
	active: { first: false, week: false, month: false },
	week: { ...REPORT.week, chat_turns: "0", onboarding: "model_ready" },
};

const PRIVATE_HEADERS = {
	"x-forwarded-for": "203.0.113.7",
	"x-real-ip": "203.0.113.7",
	"x-vercel-forwarded-for": "203.0.113.7",
	"user-agent": "SurfSense secret-agent",
	cookie: "session=abc",
};

async function post(
	body: unknown,
	{
		contentType = "application/json",
		headers = {},
	}: { contentType?: string | null; headers?: Record<string, string> } = {}
) {
	const events: PersonlessEvent[] = [];
	const request = new Request("https://usage.surfsense.com/api/usage", {
		method: "POST",
		headers: {
			...(contentType ? { "content-type": contentType } : {}),
			"x-vercel-ip-country": "JP",
			...PRIVATE_HEADERS,
			...headers,
		},
		body: typeof body === "string" ? body : JSON.stringify(body),
	});
	const response = await receiveUsageReport(request, { record: (event) => events.push(event) });
	return { response, events };
}

/** A copy of REPORT with one value replaced at a dotted path. */
function withValue(pathName: string, value: unknown) {
	const copy = structuredClone(REPORT) as Record<string, unknown>;
	const keys = pathName.split(".");
	let target = copy;
	for (const key of keys.slice(0, -1)) target = target[key] as Record<string, unknown>;
	target[keys[keys.length - 1]] = value;
	return copy;
}

test("a valid report is a 204 with no body and nothing cached", async () => {
	const { response } = await post(REPORT);
	assert.equal(response.status, 204);
	assert.equal(await response.text(), "");
	assert.equal(response.headers.get("cache-control"), "no-store");
});

test("a 2.2.4 report records one desktop_usage_report, flattened, as a daily one", async () => {
	const { events } = await post(REPORT);
	assert.deepEqual(events, [
		{
			event: "desktop_usage_report",
			properties: {
				schema: 1,
				app_version: "2.2.4",
				platform: "win32-x64",
				os: "windows-11",
				ui_language: "en",
				install_week: "2026-W43",
				trigger: "daily",
				active_first: false,
				active_week: true,
				active_month: false,
				week_chat_turns: "10-49",
				week_agent_turns: "0",
				week_model_source: "local",
				week_sources: "10-99",
				week_studio_outputs: "1-4",
				week_plugin_calls: "0",
				week_onboarding: "first_answer",
				country: "JP",
			},
		},
	]);
});

test("an install's first report carries its hardware", async () => {
	const { response, events } = await post(FIRST_REPORT);
	assert.equal(response.status, 204);
	assert.equal(events[0].properties.hardware_ram_gb, "16-31");
	assert.equal(events[0].properties.hardware_gpu, "nvidia");
	assert.equal(events[0].properties.hardware_vram_gb, "8-11");
});

test("a daily report that says so is recorded as daily", async () => {
	const { response, events } = await post({ ...REPORT, trigger: "daily" });
	assert.equal(response.status, 204);
	assert.equal(events[0].properties.trigger, "daily");
});

test("a setup report with every flag false and a week is recorded as setup", async () => {
	const { response, events } = await post(SETUP_REPORT);
	assert.equal(response.status, 204);
	assert.equal(events[0].properties.trigger, "setup");
	assert.equal(events[0].properties.active_first, false);
	assert.equal(events[0].properties.active_week, false);
	assert.equal(events[0].properties.active_month, false);
	assert.equal(events[0].properties.week_onboarding, "model_ready");
});

test("a week on a report that is not the week's first is accepted", async () => {
	const { response, events } = await post({
		...REPORT,
		active: { first: false, week: false, month: true },
	});
	assert.equal(response.status, 204);
	assert.equal(events[0].properties.week_chat_turns, "10-49");
});

test("hardware on a report that is not the install's first is accepted", async () => {
	const { response, events } = await post({ ...REPORT, hardware: FIRST_REPORT.hardware });
	assert.equal(response.status, 204);
	assert.equal(events[0].properties.hardware_gpu, "nvidia");
});

for (const gpuRuntime of ["reachable", "unreachable", "none", "unknown"]) {
	test(`hardware.gpu_runtime = ${gpuRuntime} is recorded`, async () => {
		const { response, events } = await post({
			...FIRST_REPORT,
			hardware: { ...FIRST_REPORT.hardware, gpu_runtime: gpuRuntime },
		});
		assert.equal(response.status, 204);
		assert.equal(events[0].properties.hardware_gpu_runtime, gpuRuntime);
	});
}

test("hardware without gpu_runtime records no gpu_runtime", async () => {
	const { events } = await post(FIRST_REPORT);
	assert.equal("hardware_gpu_runtime" in events[0].properties, false);
});

test("a mid-week report with neither section records only the flags", async () => {
	const { response, events } = await post({
		...REPORT,
		active: { first: false, week: false, month: false },
		week: null,
	});
	assert.equal(response.status, 204);
	const keys = Object.keys(events[0].properties);
	assert.equal(
		keys.some((key) => key.startsWith("week_") || key.startsWith("hardware_")),
		false
	);
});

test("without the country header the country is unknown", async () => {
	const request = new Request("https://usage.surfsense.com/api/usage", {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(REPORT),
	});
	const events: PersonlessEvent[] = [];
	await receiveUsageReport(request, { record: (event) => events.push(event) });
	assert.equal(events[0].properties.country, "unknown");
});

test("the recorded event carries no IP address, User-Agent or cookie", async () => {
	const { events } = await post(FIRST_REPORT);
	const recorded = JSON.stringify(events);
	assert.doesNotMatch(recorded, /203\.0\.113\.7/);
	assert.doesNotMatch(recorded, /secret-agent/);
	assert.doesNotMatch(recorded, /session=abc/);
	assert.doesNotMatch(recorded, /"\$?ip"/);
});

const UNKNOWN_KEYS: Record<string, unknown> = {
	"at the top": { ...REPORT, install_id: "abc" },
	"in a setup report": { ...SETUP_REPORT, step_at: "2026-10-27T09:00:00Z" },
	"in active": withValue("active.day", true),
	"in week": withValue("week.prompt", "hello"),
	"in hardware": { ...FIRST_REPORT, hardware: { ...FIRST_REPORT.hardware, cpu: "i9" } },
	"named __proto__": `{"__proto__": {"x": 1}, ${JSON.stringify(REPORT).slice(1)}`,
};

for (const [where, body] of Object.entries(UNKNOWN_KEYS)) {
	test(`an unknown key ${where} is a 400 and is not recorded`, async () => {
		const { response, events } = await post(body);
		assert.equal(response.status, 400);
		assert.equal(events.length, 0);
	});
}

const BAD_VALUES: Array<[string, unknown]> = [
	["schema", 2],
	["app_version", "2.2.4-beta"],
	["app_version", "latest"],
	["platform", "win32-ia32"],
	["os", "windows-7"],
	["os", "macos-"],
	["ui_language", "fr"],
	["install_week", "2026-43"],
	["install_week", "2026-W54"],
	["active.first", "yes"],
	["week.chat_turns", "5"],
	["week.chat_turns", 5],
	["week.model_source", "openai"],
	["week.sources", "10-49"],
	["week.studio_outputs", "1-9"],
	["week.plugin_calls", "10-49"],
	["week.onboarding", "done"],
	["week", "busy"],
	["trigger", "weekly"],
	["trigger", "Setup"],
	["trigger", null],
	["hardware", { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11", gpu_runtime: "broken" }],
	["hardware", { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11", gpu_runtime: null }],
];

for (const [pathName, value] of BAD_VALUES) {
	test(`${pathName} = ${JSON.stringify(value)} is a 400`, async () => {
		const { response, events } = await post(withValue(pathName, value));
		assert.equal(response.status, 400);
		assert.equal(events.length, 0);
	});
}

test("a missing key is a 400", async () => {
	const { hardware: _hardware, ...withoutHardware } = REPORT;
	const { response } = await post(withoutHardware);
	assert.equal(response.status, 400);
});

test("a body that is not JSON is a 400", async () => {
	for (const body of ["", "{", "null", "[]", "1"]) {
		const { response } = await post(body);
		assert.equal(response.status, 400, JSON.stringify(body));
	}
});

test("a body over 4 KB is a 413", async () => {
	const padded = `${JSON.stringify(REPORT)}${" ".repeat(4097)}`;
	const { response, events } = await post(padded);
	assert.equal(response.status, 413);
	assert.equal(events.length, 0);
});

test("a body over 4 KB with no Content-Length is a 413 and is not read to the end", async () => {
	let pulled = 0;
	const endless = new ReadableStream<Uint8Array>({
		pull(controller) {
			pulled += 1;
			controller.enqueue(new Uint8Array(1024).fill(32));
		},
	});
	const request = new Request("https://usage.surfsense.com/api/usage", {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: endless,
		duplex: "half",
	} as RequestInit);
	const response = await receiveUsageReport(request, { record: () => {} });
	assert.equal(response.status, 413);
	assert.ok(pulled < 10, `pulled ${pulled} chunks`);
});

test("a body of exactly 4 KB is accepted", async () => {
	const json = JSON.stringify(REPORT);
	const { response } = await post(`${json}${" ".repeat(4096 - json.length)}`);
	assert.equal(response.status, 204);
});

test("a body that is not JSON content is a 415", async () => {
	for (const contentType of [null, "text/plain", "application/x-www-form-urlencoded"]) {
		const { response, events } = await post(REPORT, { contentType });
		assert.equal(response.status, 415, String(contentType));
		assert.equal(events.length, 0);
	}
});

test("JSON with a charset parameter is accepted", async () => {
	const { response } = await post(REPORT, { contentType: "application/json; charset=utf-8" });
	assert.equal(response.status, 204);
});
