import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { mock, test } from "node:test";

// Run with: pnpm exec tsx --test features/desktop-telemetry/update-feed/update-feed.test.ts

import type { PersonlessEvent } from "../personless-capture";
import type { FetchManifest } from "./latest-github-manifest";
import { serveUpdateManifest } from "./serve-update-manifest";

// Fetched once from releases/latest/download on 21 Oct 2026 (v2.2.3).
const fixture = (name: string) => readFileSync(path.join(__dirname, "fixtures", name), "utf8");
const PINNED = "https://github.com/MODSetter/SurfSense/releases/download/v2.2.3/";

const CLIENT_HEADERS = {
	"x-surfsense-version": "2.2.4",
	"x-surfsense-platform": "win32-x64",
	"x-surfsense-os": "windows-11",
	"x-vercel-ip-country": "DE",
	"x-forwarded-for": "203.0.113.7",
	"x-real-ip": "203.0.113.7",
	"x-vercel-forwarded-for": "203.0.113.7",
	"user-agent": "electron-builder secret-agent",
	cookie: "session=abc",
};

type Call = { url: string; init: Parameters<FetchManifest>[1] };

function upstream(body: string | (() => Promise<Response>), status = 200) {
	const calls: Call[] = [];
	const fetchManifest: FetchManifest = async (url, init) => {
		calls.push({ url, init });
		return typeof body === "function" ? body() : new Response(body, { status });
	};
	return { calls, fetchManifest };
}

async function check(
	file: string,
	manifest: string | (() => Promise<Response>),
	{
		status = 200,
		headers = CLIENT_HEADERS,
		method = "GET",
	}: { status?: number; headers?: Record<string, string>; method?: string } = {}
) {
	const events: PersonlessEvent[] = [];
	const { calls, fetchManifest } = upstream(manifest, status);
	const request = new Request(`https://updates.surfsense.com/api/updates/${file}?noCache=1`, {
		method,
		headers,
	});
	const response = await serveUpdateManifest(request, file, {
		fetchManifest,
		record: (event) => events.push(event),
	});
	return { response, body: await response.text(), events, calls };
}

mock.method(console, "warn", () => {});

for (const file of ["stable.yml", "stable-mac.yml", "stable-linux.yml"]) {
	test(`${file} from GitHub is served with every file pinned to its release`, async () => {
		const original = fixture(file);
		const { response, body } = await check(file, original);

		assert.equal(response.status, 200);
		assert.equal(response.headers.get("content-type"), "text/yaml");
		assert.equal(response.headers.get("cache-control"), "no-store");

		const before = original.trimEnd().split("\n");
		const after = body.trimEnd().split("\n");
		assert.equal(after.length, before.length);
		for (const [index, line] of after.entries()) {
			const match = /^(\s*- url|path): (.*)$/.exec(line);
			if (match) {
				const name = before[index].split(": ")[1];
				assert.equal(match[2], `${PINNED}${name}`, line);
			} else {
				// sha512, size, blockMapSize, releaseDate and version pass through untouched.
				assert.equal(line, before[index]);
			}
		}
	});
}

// electron-builder's rpm target writes itself into stable-linux.yml beside the
// deb, with a sha512 and size but no blockMapSize.
const LINUX_WITH_RPM = fixture("stable-linux.yml").replace(
	"path: SurfSense.AppImage",
	[
		"  - url: SurfSense.rpm",
		"    sha512: 8DeRyFZuqd1BnqF98baazD7Yp9DHjBBVW9TRfd+a3NH7SrxXIgAHEZyIneBSanCYgX0hAMxfyw5lyHVmq2k75w==",
		"    size: 1301442310",
		"path: SurfSense.AppImage",
	].join("\n")
);

test("stable-linux.yml listing the rpm is served with the rpm pinned to its release too", async () => {
	assert.ok(LINUX_WITH_RPM.includes("url: SurfSense.rpm"));
	const { response, body } = await check("stable-linux.yml", LINUX_WITH_RPM);
	assert.equal(response.status, 200);
	assert.ok(body.split("\n").includes(`  - url: ${PINNED}SurfSense.rpm`), body);
});

test("stable-linux-arm64.yml is a channel file too", async () => {
	const { response } = await check("stable-linux-arm64.yml", fixture("stable-linux.yml"));
	assert.equal(response.status, 200);
});

test("a manifest already pinned to its own release is served as it is", async () => {
	const pinned = (await check("stable.yml", fixture("stable.yml"))).body;
	const { response, body } = await check("stable.yml", pinned);
	assert.equal(response.status, 200);
	assert.equal(body, pinned);
});

test("stagingPercentage passes through untouched", async () => {
	const staged = `${fixture("stable.yml")}stagingPercentage: 25\n`;
	const { response, body } = await check("stable.yml", staged);
	assert.equal(response.status, 200);
	assert.match(body, /\nstagingPercentage: 25\n$/);
});

test("GitHub's latest release is fetched with nothing from the app's request", async () => {
	const { calls } = await check("stable-mac.yml", fixture("stable-mac.yml"));
	assert.equal(calls.length, 1);
	assert.equal(
		calls[0].url,
		"https://github.com/MODSetter/SurfSense/releases/latest/download/stable-mac.yml"
	);
	assert.equal(calls[0].init.redirect, "follow");
	assert.equal(calls[0].init.next?.revalidate, 900);
	assert.equal(calls[0].init.headers, undefined);
});

for (const file of [
	"latest.yml",
	"latest-mac.yml",
	"latest-linux.yml",
	"stable.yaml",
	"stable-windows.yml",
	"stable-linux-arm.yml",
	"STABLE.yml",
	"beta.yml",
	"stable.yml.exe",
	"../stable.yml",
	"stable.yml/..",
	"",
]) {
	test(`${JSON.stringify(file)} is not a channel file: 404, no fetch, nothing recorded`, async () => {
		const { response, events, calls } = await check(file, fixture("stable.yml"));
		assert.equal(response.status, 404);
		assert.equal(response.headers.get("cache-control"), "no-store");
		assert.equal(calls.length, 0);
		assert.equal(events.length, 0);
	});
}

const stable = fixture("stable.yml");
const HOSTILE: Record<string, string> = {
	"an absolute url off GitHub": stable.replace(
		"url: SurfSense-Setup.exe",
		"url: https://evil.example/SurfSense-Setup.exe"
	),
	"a GitHub url for another release": stable.replace(
		"url: SurfSense-Setup.exe",
		"url: https://github.com/MODSetter/SurfSense/releases/download/v2.2.2/SurfSense-Setup.exe"
	),
	"a GitHub url for another repository": stable.replace(
		"path: SurfSense-Setup.exe",
		"path: https://github.com/someone/SurfSense/releases/download/v2.2.3/SurfSense-Setup.exe"
	),
	"path traversal in a url": stable.replace(
		"url: SurfSense-Setup.exe",
		"url: ../../../evil/SurfSense-Setup.exe"
	),
	"path traversal after the name": stable.replace(
		"path: SurfSense-Setup.exe",
		"path: SurfSense/../../x/SurfSense-Setup.exe"
	),
	"a file that is not an installer": stable.replace(
		"url: SurfSense-Setup.exe",
		"url: SurfSense-Setup.sh"
	),
	// The snap updates from the Snap Store, so no manifest of ours names it.
	"a snap": stable.replace("url: SurfSense-Setup.exe", "url: SurfSense.snap"),
	"a file not named SurfSense": stable.replace("path: SurfSense-Setup.exe", "path: Setup.exe"),
	"a quoted url": stable.replace(
		"url: SurfSense-Setup.exe",
		"url: 'https://evil.example/SurfSense-Setup.exe'"
	),
	"a missing version": stable.replace("version: 2.2.3\n", ""),
	"a version that is not x.y.z": stable.replace("version: 2.2.3", "version: 2.2.3-evil"),
	"two versions": `version: 9.9.9\n${stable}`,
	"two paths": `${stable}path: SurfSense-Setup.exe\n`,
	"a flow mapping file entry": stable.replace(
		"  - url: SurfSense-Setup.exe",
		"  - {url: 'https://evil.example/x.exe', sha512: x}"
	),
	"a folded url": stable.replace(
		"  - url: SurfSense-Setup.exe",
		"  - url: SurfSense-Setup.exe\n      https://evil.example/x.exe"
	),
	"an unknown key": `${stable}releaseNotes: hello\n`,
	"a comment": `# hi\n${stable}`,
	"a document marker": `---\n${stable}`,
	"windows line endings": stable.replace(/\n/g, "\r\n"),
	"a file field outside files:": stable.replace("releaseDate:", "    size: 1\nreleaseDate:"),
	"no files at all": "version: 2.2.3\npath: SurfSense-Setup.exe\n",
	"an empty body": "",
	"an HTML error page": "<html><body>Not Found</body></html>",
};

for (const [name, manifest] of Object.entries(HOSTILE)) {
	test(`a manifest with ${name} is a 502`, async () => {
		const { response, body } = await check("stable.yml", manifest);
		assert.equal(response.status, 502);
		assert.equal(response.headers.get("cache-control"), "no-store");
		assert.doesNotMatch(body, /evil/);
	});
}

test("GitHub not answering 200 is a 502", async () => {
	for (const status of [404, 403, 500, 503]) {
		const { response } = await check("stable.yml", "Not Found", { status });
		assert.equal(response.status, 502, String(status));
	}
});

test("GitHub failing outright is a 502", async () => {
	const { response } = await check("stable.yml", () => Promise.reject(new Error("timeout")));
	assert.equal(response.status, 502);
});

test("a manifest over 64 KB is a 502, even when every line is valid", async () => {
	// Repeats the fixture's own file entry, so only the size cap can refuse it.
	const cap = 64 * 1024;
	const entry = `${stable.split("\n").slice(2, 5).join("\n")}\n`;
	const withEntries = (count: number) =>
		stable.replace("files:\n", `files:\n${entry.repeat(count)}`);
	const under = withEntries(Math.floor((cap - stable.length) / entry.length));
	const over = withEntries(Math.floor((cap - stable.length) / entry.length) + 1);
	assert.ok(under.length <= cap && over.length > cap);

	assert.equal((await check("stable.yml", under)).response.status, 200);
	assert.equal((await check("stable.yml", over)).response.status, 502);
});

test("each check records one desktop_update_check with exactly the contract's fields", async () => {
	const { events } = await check("stable.yml", stable);
	assert.deepEqual(events, [
		{
			event: "desktop_update_check",
			properties: {
				file: "stable.yml",
				app_version: "2.2.4",
				platform: "win32-x64",
				os: "windows-11",
				country: "DE",
			},
		},
	]);
});

test("a HEAD request is answered but not recorded, since the app only GETs", async () => {
	const { response, events } = await check("stable.yml", stable, { method: "HEAD" });
	assert.equal(response.status, 200);
	assert.equal(events.length, 0);
});

test("a check is recorded even when GitHub fails, since the app still checked", async () => {
	const { events } = await check("stable-mac.yml", "nope", { status: 500 });
	assert.equal(events.length, 1);
	assert.equal(events[0].properties.file, "stable-mac.yml");
});

test("headers outside the contract fold into invalid, other and unknown", async () => {
	const { events } = await check("stable-linux.yml", fixture("stable-linux.yml"), {
		headers: {
			"x-surfsense-version": "2.2.4-beta+alice",
			"x-surfsense-platform": "freebsd-x64",
			"x-surfsense-os": "windows-7",
			"x-vercel-ip-country": "not a country",
		},
	});
	assert.deepEqual(events[0].properties, {
		file: "stable-linux.yml",
		app_version: "invalid",
		platform: "other",
		os: "other",
		country: "unknown",
	});
});

test("a check with no SurfSense headers still counts, as invalid, other and unknown", async () => {
	const { events } = await check("stable.yml", stable, { headers: {} });
	assert.deepEqual(events[0].properties, {
		file: "stable.yml",
		app_version: "invalid",
		platform: "other",
		os: "other",
		country: "unknown",
	});
});

test("every macOS major is accepted as its own OS", async () => {
	for (const os of ["macos-11", "macos-15", "macos-26"]) {
		const { events } = await check("stable-mac.yml", fixture("stable-mac.yml"), {
			headers: { "x-surfsense-os": os, "x-surfsense-platform": "darwin-arm64" },
		});
		assert.equal(events[0].properties.os, os);
		assert.equal(events[0].properties.platform, "darwin-arm64");
	}
});

test("the recorded event carries no IP address, User-Agent or cookie", async () => {
	const { events } = await check("stable.yml", stable);
	const recorded = JSON.stringify(events);
	assert.doesNotMatch(recorded, /203\.0\.113\.7/);
	assert.doesNotMatch(recorded, /secret-agent|electron-builder/);
	assert.doesNotMatch(recorded, /session=abc/);
	assert.doesNotMatch(recorded, /"\$?ip"/);
});
