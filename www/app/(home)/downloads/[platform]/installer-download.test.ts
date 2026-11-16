import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test app/(home)/downloads/[platform]/installer-download.test.ts

import { NextRequest } from "next/server";
import { isAutomatedFetch } from "@/app/(home)/downloads/[platform]/automated-fetch";
import { installerRedirect } from "@/app/(home)/downloads/[platform]/installer-redirect";
import { countryFromHeader } from "@/app/(home)/downloads/[platform]/installer-request";
import {
	type PublishedInstallers,
	parsePublishedInstallers,
} from "@/app/(home)/downloads/[platform]/published-installers";
import {
	type InstallerDownload,
	installerDownloadMessage,
} from "@/app/(home)/downloads/[platform]/record-installer-download";
import {
	APP_RELEASE_VERSION,
	getAssetLabel,
	INSTALLER_FILES,
	isOfferedInstaller,
	platformOfAsset,
} from "@/features/downloads/app-release";

const RELEASES = "https://github.com/MODSetter/SurfSense/releases/download";
const LATEST = "https://github.com/MODSetter/SurfSense/releases/latest/download";
const BROWSER =
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const ALL_FILES = new Set(Object.values(INSTALLER_FILES));

function publishedTags(...versions: string[]): PublishedInstallers {
	return new Map(versions.map((version) => [`v${version}`, ALL_FILES]));
}

const PINNED_PUBLISHED = publishedTags(APP_RELEASE_VERSION);

function request(
	path: string,
	init: { method?: string; userAgent?: string; country?: string } = {}
): NextRequest {
	const headers: Record<string, string> = { "user-agent": init.userAgent ?? BROWSER };
	if (init.country) headers["x-vercel-ip-country"] = init.country;
	return new NextRequest(`https://www.surfsense.com${path}`, {
		method: init.method ?? "GET",
		headers,
	});
}

function context(platform: string) {
	return { params: Promise.resolve({ platform }) };
}

/** The redirect with GitHub, PostHog and Next's `after()` stood in for. */
function redirectWith(
	published: PublishedInstallers | null | Error = PINNED_PUBLISHED,
	options: { afterThrows?: boolean } = {}
) {
	const downloads: InstallerDownload[] = [];
	const pending: (() => Promise<void>)[] = [];
	const { GET, HEAD } = installerRedirect({
		publishedInstallers: async () => {
			if (published instanceof Error) throw published;
			return published;
		},
		recordDownload: async (download) => {
			downloads.push(download);
		},
		afterResponse: (task) => {
			if (options.afterThrows) throw new Error("after() outside a request scope");
			pending.push(task);
		},
	});
	async function counted(): Promise<InstallerDownload[]> {
		for (const task of pending.splice(0)) await task();
		return downloads;
	}
	return { GET, HEAD, downloads, counted };
}

async function locationOf(path: string, published?: PublishedInstallers | null) {
	const platform = new URL(path, "https://x").pathname.split("/").at(-1) ?? "";
	const response = await redirectWith(published).GET(request(path), context(platform));
	return response.headers.get("location");
}

test("each platform redirects to its installer on the pinned release once GitHub serves it", async () => {
	for (const [platform, file] of Object.entries(INSTALLER_FILES)) {
		assert.equal(
			await locationOf(`/downloads/${platform}`),
			`${RELEASES}/v${APP_RELEASE_VERSION}/${file}`
		);
	}
});

test("a pinned release still in draft sends every link to Latest instead", async () => {
	// Vercel deploys the new pin while the release is still a draft, whose assets 404.
	const redirect = redirectWith(publishedTags("2.2.2"));
	const response = await redirect.GET(request("/downloads/windows?src=readme"), context("windows"));
	assert.equal(response.headers.get("location"), `${LATEST}/SurfSense-Setup.exe`);
	assert.equal((await redirect.counted())[0]?.version, "latest");
});

test("a release missing one platform's file sends that platform to Latest", async () => {
	const partial: PublishedInstallers = new Map([
		[`v${APP_RELEASE_VERSION}`, new Set(["SurfSense-Setup.exe"])],
	]);
	assert.equal(await locationOf("/downloads/mac", partial), `${LATEST}/SurfSense-arm64.dmg`);
	assert.equal(
		await locationOf("/downloads/windows", partial),
		`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-Setup.exe`
	);
});

test("with GitHub unreachable the link still reaches an installer", async () => {
	assert.equal(await locationOf("/downloads/linux-deb", null), `${LATEST}/SurfSense.deb`);
	const response = await redirectWith(new Error("rate limited")).GET(
		request("/downloads/linux-deb"),
		context("linux-deb")
	);
	assert.equal(response.status, 302);
	assert.equal(response.headers.get("location"), `${LATEST}/SurfSense.deb`);
});

test("a pinned tag at or after 2.0.2 keeps its build", async () => {
	const published = publishedTags("2.0.2", "2.1.0", APP_RELEASE_VERSION);
	for (const [v, version] of [
		["v2.0.2", "2.0.2"],
		["2.1.0", "2.1.0"],
	]) {
		assert.equal(
			await locationOf(`/downloads/mac?v=${v}`, published),
			`${RELEASES}/v${version}/SurfSense-arm64.dmg`,
			v
		);
	}
});

test("a tag that was never published goes to Latest", async () => {
	for (const v of ["v2.0.4", "v10.0.0"]) {
		assert.equal(await locationOf(`/downloads/mac?v=${v}`), `${LATEST}/SurfSense-arm64.dmg`, v);
	}
});

test("an older, prerelease or malformed tag falls back to the pinned release", async () => {
	// 2.0.0 and 2.0.1 put the version in their file names, so the fixed names 404 there.
	const published = publishedTags("2.0.0", "2.0.1", APP_RELEASE_VERSION);
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
		assert.equal(
			await locationOf(`/downloads/windows?v=${encodeURIComponent(v)}`, published),
			`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-Setup.exe`,
			v
		);
	}
});

test("only published releases count, never a draft", () => {
	const published = parsePublishedInstallers([
		{ tag_name: "v2.3.0", draft: true, assets: [{ name: "SurfSense-Setup.exe" }] },
		{ tag_name: "v2.2.3", draft: false, assets: [{ name: "SurfSense-Setup.exe" }, {}] },
		{ tag_name: "v2.2.2", assets: [{ name: "SurfSense-Setup.exe" }] },
		null,
	]);
	assert.deepEqual([...published.keys()], ["v2.2.3"]);
	assert.deepEqual([...(published.get("v2.2.3") ?? [])], ["SurfSense-Setup.exe"]);
	assert.equal(parsePublishedInstallers({ message: "API rate limit exceeded" }).size, 0);
});

test("a browser's GET counts one download, after the redirect is sent", async () => {
	const redirect = redirectWith();
	const response = await redirect.GET(
		request("/downloads/linux-deb?src=README", { country: "de" }),
		context("linux-deb")
	);
	assert.equal(response.status, 302);
	assert.equal(response.headers.get("cache-control"), "no-store");
	assert.deepEqual(redirect.downloads, [], "counted before the response was sent");
	assert.deepEqual(await redirect.counted(), [
		{ platform: "linux-deb", src: "readme", version: APP_RELEASE_VERSION, country: "DE" },
	]);
});

test("src keeps the known channels and counts anything else as other", async () => {
	for (const [src, expected] of [
		...["site", "readme", "email", "app", "pricing", "other"].map((s) => [s, s]),
		["you@x.com", "other"],
		["", "other"],
	]) {
		const redirect = redirectWith();
		await redirect.GET(
			request(`/downloads/windows?src=${encodeURIComponent(src)}`),
			context("windows")
		);
		assert.equal((await redirect.counted())[0]?.src, expected, src);
	}
});

test("a bot, a mail scanner or a HEAD is redirected but never counted", async () => {
	const redirect = redirectWith();
	for (const userAgent of ["curl/8.7.1", "Barracuda Sentinel (EE)", ""]) {
		const response = await redirect.GET(
			request("/downloads/windows", { userAgent }),
			context("windows")
		);
		assert.equal(
			response.headers.get("location"),
			`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-Setup.exe`
		);
	}
	const head = await redirect.HEAD(request("/downloads/mac", { method: "HEAD" }), context("mac"));
	assert.equal(head.status, 302);
	assert.equal(
		head.headers.get("location"),
		`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-arm64.dmg`
	);
	assert.equal(head.headers.get("cache-control"), "no-store");
	assert.deepEqual(await redirect.counted(), []);
});

test("analytics failing never costs the redirect", async () => {
	const response = await redirectWith(PINNED_PUBLISHED, { afterThrows: true }).GET(
		request("/downloads/windows"),
		context("windows")
	);
	assert.equal(response.status, 302);
	assert.equal(
		response.headers.get("location"),
		`${RELEASES}/v${APP_RELEASE_VERSION}/SurfSense-Setup.exe`
	);
});

test("an unknown platform goes back to the downloads page, uncounted", async () => {
	for (const platform of ["amiga", "linux", "WINDOWS", "toString", "__proto__"]) {
		const redirect = redirectWith();
		const response = await redirect.GET(
			request(`/downloads/${encodeURIComponent(platform)}`),
			context(platform)
		);
		assert.equal(response.status, 302, platform);
		assert.equal(response.headers.get("location"), "https://www.surfsense.com/downloads");
		assert.deepEqual(await redirect.counted(), [], platform);
	}
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
	assert.equal(platformOfAsset("SurfSense.rpm"), "linux-rpm");
	assert.equal(platformOfAsset("SurfSense-arm64.zip"), null);
	assert.equal(platformOfAsset("latest.yml"), null);
	assert.equal(platformOfAsset("SurfSense.snap"), null);
	assert.equal(platformOfAsset("install.sh"), null);
	assert.equal(platformOfAsset("SHA256SUMS"), null);
});

test("the site offers each installer a person downloads, rpm included", () => {
	for (const name of [
		"SurfSense-Setup.exe",
		"SurfSense-arm64.dmg",
		"SurfSense.AppImage",
		"SurfSense.deb",
		"SurfSense.rpm",
	]) {
		assert.equal(isOfferedInstaller(name), true, name);
	}
	assert.equal(getAssetLabel("SurfSense.rpm"), "Linux (rpm)");
});

test("update files, checksums, install scripts, the apt index and the snap stay off the site", () => {
	// The snap installs from the Snap Store, and the rest are read by tools, not people.
	for (const name of [
		"SurfSense-arm64.zip",
		"SurfSense-Setup.exe.blockmap",
		"stable-linux.yml",
		"SurfSense.snap",
		"SHA256SUMS",
		"install.sh",
		"install.ps1",
		"Packages",
		"Packages.gz",
		"Release",
		"Release.gpg",
		"InRelease",
		"surfsense-archive-keyring.gpg",
	]) {
		assert.equal(isOfferedInstaller(name), false, name);
	}
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
