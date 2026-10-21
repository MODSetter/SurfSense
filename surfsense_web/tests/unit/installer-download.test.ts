import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test tests/unit/installer-download.test.ts

import { NextRequest } from "next/server";
import { isAutomatedFetch } from "@/app/(home)/downloads/[platform]/automated-fetch";
import {
	countryFromHeader,
	readInstallerRequest,
} from "@/app/(home)/downloads/[platform]/installer-request";
import { installerDownloadMessage } from "@/app/(home)/downloads/[platform]/record-installer-download";
import { GET, HEAD } from "@/app/(home)/downloads/[platform]/route";
import { APP_RELEASE_VERSION, INSTALLER_FILES, platformOfAsset } from "@/lib/app-release";

const RELEASES = "https://github.com/MODSetter/SurfSense/releases/download";
const BROWSER =
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";

function request(path: string, init: { method?: string; userAgent?: string } = {}) {
	return new NextRequest(`https://www.surfsense.com${path}`, {
		method: init.method ?? "GET",
		headers: { "user-agent": init.userAgent ?? BROWSER },
	});
}

function context(platform: string) {
	return { params: Promise.resolve({ platform }) };
}

test("each platform names its installer on the pinned release by default", () => {
	for (const [platform, file] of Object.entries(INSTALLER_FILES)) {
		const target = readInstallerRequest(platform, new URLSearchParams());
		assert.equal(target?.assetUrl, `${RELEASES}/v${APP_RELEASE_VERSION}/${file}`);
		assert.equal(target?.version, APP_RELEASE_VERSION);
		assert.equal(target?.src, "other");
	}
});

test("an unknown platform is no installer", () => {
	for (const platform of ["", "linux", "WINDOWS", "toString", "__proto__", "../mac"]) {
		assert.equal(readInstallerRequest(platform, new URLSearchParams()), null, platform);
	}
});

test("a pinned tag at or after 2.0.2 keeps its build", () => {
	for (const [v, version] of [
		["v2.0.2", "2.0.2"],
		["2.1.0", "2.1.0"],
		["v10.0.0", "10.0.0"],
	]) {
		const target = readInstallerRequest("mac", new URLSearchParams({ v }));
		assert.equal(target?.version, version, v);
		assert.equal(target?.assetUrl, `${RELEASES}/v${version}/SurfSense-arm64.dmg`);
	}
});

test("an older, prerelease or malformed tag falls back to the pinned release", () => {
	// 2.0.0 and 2.0.1 put the version in their file names, so the fixed names 404 there.
	for (const v of [
		"v2.0.1",
		"v2.0.0",
		"v0.0.40",
		"v2.3.0-beta.1",
		"latest",
		"2.2",
		"",
		"v99999.0.0",
	]) {
		const target = readInstallerRequest("windows", new URLSearchParams({ v }));
		assert.equal(target?.version, APP_RELEASE_VERSION, v);
	}
});

test("src keeps the known channels and counts anything else as other", () => {
	for (const src of ["site", "readme", "email", "app", "pricing", "other"]) {
		assert.equal(readInstallerRequest("windows", new URLSearchParams({ src }))?.src, src);
	}
	assert.equal(
		readInstallerRequest("windows", new URLSearchParams({ src: "README" }))?.src,
		"readme"
	);
	assert.equal(
		readInstallerRequest("windows", new URLSearchParams({ src: "you@x.com" }))?.src,
		"other"
	);
});

test("only a two-letter country is kept", () => {
	assert.equal(countryFromHeader("in"), "IN");
	assert.equal(countryFromHeader("US"), "US");
	for (const value of [null, "", "XXX", "1A", "203.0.113.4"]) {
		assert.equal(countryFromHeader(value), null, String(value));
	}
});

test("crawlers, previews and mail scanners are not downloads", () => {
	for (const agent of [
		"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
		"Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
		"Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
		"facebookexternalhit/1.1",
		"WhatsApp/2.23.20.0",
		"Microsoft Office/16.0 (Windows NT 10.0; Microsoft Outlook 16.0.17531; Pro)",
		"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36",
		"python-requests/2.32.3",
		"curl/8.7.1",
		"Wget/1.21.4",
		"Go-http-client/2.0",
		"Barracuda Sentinel (EE)",
		"",
		null,
	]) {
		assert.equal(isAutomatedFetch(agent), true, String(agent));
	}
});

test("ordinary browsers are downloads", () => {
	for (const agent of [
		BROWSER,
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
		"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
	]) {
		assert.equal(isAutomatedFetch(agent), false, agent);
	}
});

test("the grid's assets map back to their platforms", () => {
	assert.equal(platformOfAsset("SurfSense-Setup.exe"), "windows");
	assert.equal(platformOfAsset("SurfSense-arm64.dmg"), "mac");
	assert.equal(platformOfAsset("SurfSense.AppImage"), "linux-appimage");
	assert.equal(platformOfAsset("SurfSense.deb"), "linux-deb");
	assert.equal(platformOfAsset("SurfSense-arm64.zip"), null);
	assert.equal(platformOfAsset("latest.yml"), null);
});

test("GET redirects to the installer, uncached, even with analytics unconfigured", async () => {
	const response = await GET(
		request("/downloads/linux-deb?src=readme&v=v2.2.2"),
		context("linux-deb")
	);
	assert.equal(response.status, 302);
	assert.equal(response.headers.get("location"), `${RELEASES}/v2.2.2/SurfSense.deb`);
	assert.equal(response.headers.get("cache-control"), "no-store");
});

test("a bot still gets the redirect", async () => {
	const response = await GET(
		request("/downloads/windows", { userAgent: "curl/8.7.1" }),
		context("windows")
	);
	assert.equal(response.status, 302);
	assert.equal(
		response.headers.get("location"),
		`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-Setup.exe`
	);
});

test("an unknown platform goes back to the downloads page", async () => {
	const response = await GET(request("/downloads/amiga"), context("amiga"));
	assert.equal(response.status, 302);
	assert.equal(response.headers.get("location"), "https://www.surfsense.com/downloads");
});

test("HEAD redirects the same way", async () => {
	const response = await HEAD(request("/downloads/mac", { method: "HEAD" }), context("mac"));
	assert.equal(response.status, 302);
	assert.equal(
		response.headers.get("location"),
		`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-arm64.dmg`
	);
});

test("the download event is personless and carries only platform, source, version and country", () => {
	const message = installerDownloadMessage(
		{ platform: "windows", src: "email", version: "2.2.3", country: "DE" },
		"event-1"
	);
	assert.equal(message.event, "installer_download");
	assert.equal(message.distinctId, "event-1");
	assert.equal(message.disableGeoip, true);
	assert.deepEqual(message.properties, {
		platform: "windows",
		src: "email",
		version: "2.2.3",
		country: "DE",
		$process_person_profile: false,
	});
});

test("each download gets its own id, so downloads never join up", () => {
	const download = { platform: "mac", src: "site" as const, version: "2.2.3", country: null };
	const first = installerDownloadMessage(download);
	const second = installerDownloadMessage(download);
	assert.notEqual(first.distinctId, second.distinctId);
	assert.equal("country" in (first.properties ?? {}), false);
});
