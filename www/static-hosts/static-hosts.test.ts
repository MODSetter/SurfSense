import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";

// Run with: pnpm exec tsx --test static-hosts/static-hosts.test.ts

const HERE = import.meta.dirname;
const PUBLIC = path.join(HERE, "public");
const REGISTRY = path.join(HERE, "..", "..", "backend", "plugins", "registry");

type Has = { type: "host"; value: string }[];
type Rewrite = { source: string; destination: string; has?: Has };
type HeaderRule = { source: string; has?: Has; headers: { key: string; value: string }[] };
const config: { outputDirectory: string; rewrites: Rewrite[]; headers: HeaderRule[] } = JSON.parse(
	readFileSync(path.join(HERE, "vercel.json"), "utf8")
);

/** The served copy beside the registry file it mirrors, by request path. */
const MIRRORED: Record<string, string> = {
	"/plugins.json": "published/plugins.json",
	"/plugins.json.sig": "published/plugins.json.sig",
	"/icons/deepwiki.svg": "icons/deepwiki.svg",
	"/icons/notion.svg": "icons/notion.svg",
	"/oauth/client.json": "oauth/client.json",
	"/oauth/callback.html": "oauth/callback.html",
};

/**
 * Installed 2.x apps sign in to OAuth plugins with this file's URL as their client id, and
 * the authorization servers they registered with hold this exact document. Never edit it.
 */
const CLIENT_JSON_SHA256 = "fc49091951aa892b008b472f32302236e40682353ca792d9c34938b504ece669";

// A Windows checkout may hold the registry sources with CRLF; what Caddy served is the blob.
const asCommitted = (bytes: Buffer) =>
	Buffer.from(bytes.toString("latin1").replace(/\r\n/g, "\n"), "latin1");

function matches(rule: { source: string; has?: Has }, pathname: string, host: string) {
	if (rule.has && !rule.has.every((condition) => condition.value === host)) return false;
	if (rule.source === "/(.*)") return true;
	if (rule.source.endsWith("/(.*)")) return pathname.startsWith(rule.source.slice(0, -4));
	return rule.source === pathname;
}

/** Vercel's answer for a path: the file a rewrite (or the path itself) names, and its headers. */
function serve(pathname: string, host = "plugins.surfsense.com") {
	const rewrite = config.rewrites.find((rule) => matches(rule, pathname, host));
	const file = rewrite ? rewrite.destination : pathname;
	const headers: Record<string, string> = {};
	for (const rule of config.headers.filter((candidate) => matches(candidate, pathname, host))) {
		for (const { key, value } of rule.headers) headers[key.toLowerCase()] = value;
	}
	return { file, headers };
}

function served(file: string) {
	return readFileSync(path.join(PUBLIC, file));
}

function listFiles(dir: string, prefix = ""): string[] {
	return readdirSync(dir).flatMap((name) => {
		const full = path.join(dir, name);
		return statSync(full).isDirectory()
			? listFiles(full, `${prefix}/${name}`)
			: [`${prefix}/${name}`];
	});
}

test("the output directory is public/", () => {
	assert.equal(config.outputDirectory, "public");
});

test("every served registry file is byte for byte the registry's committed file", () => {
	for (const [file, source] of Object.entries(MIRRORED)) {
		assert.deepEqual(
			served(file),
			asCommitted(readFileSync(path.join(REGISTRY, source))),
			`${file} differs from backend/plugins/registry/${source}; copy it with git show`
		);
	}
});

test("the served files carry no CR, so a checkout can't change their bytes", () => {
	for (const file of listFiles(PUBLIC)) {
		assert.equal(served(file).includes(0x0d), false, file);
	}
});

test("client.json is the exact document installed apps sign in with", () => {
	assert.equal(
		createHash("sha256").update(served("/oauth/client.json")).digest("hex"),
		CLIENT_JSON_SHA256
	);
	const client = JSON.parse(served("/oauth/client.json").toString("utf8"));
	assert.equal(client.client_id, "https://plugins.surfsense.com/oauth/client.json");
	assert.deepEqual(client.redirect_uris, ["https://plugins.surfsense.com/oauth/callback"]);
});

test("nothing is served that the registry container did not serve", () => {
	const allowed = new Set([...Object.keys(MIRRORED), "/_health/plugins.txt", "/_health/api.json"]);
	assert.deepEqual(
		listFiles(PUBLIC).filter((file) => !allowed.has(file)),
		[]
	);
});

// The headers from backend/plugins/registry/Caddyfile, path by path.
const COMMON = { "x-content-type-options": "nosniff", "referrer-policy": "no-referrer" };
const PUBLIC_5_MIN = "public, max-age=300";

test("each path gets the registry container's headers", () => {
	const expected: Record<string, Record<string, string>> = {
		"/plugins.json": {
			...COMMON,
			"content-type": "application/json",
			"cache-control": PUBLIC_5_MIN,
		},
		"/plugins.json.sig": {
			...COMMON,
			"content-type": "text/plain; charset=utf-8",
			"cache-control": PUBLIC_5_MIN,
		},
		"/icons/deepwiki.svg": {
			...COMMON,
			"cache-control": PUBLIC_5_MIN,
			"content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
		},
		"/oauth/client.json": {
			...COMMON,
			"content-type": "application/json",
			"cache-control": PUBLIC_5_MIN,
		},
		"/oauth/callback": {
			...COMMON,
			"content-type": "text/html; charset=utf-8",
			"cache-control": "no-store",
			"content-security-policy": "frame-ancestors 'none'",
		},
		"/health": {
			...COMMON,
			"content-type": "text/plain; charset=utf-8",
			"cache-control": "no-store",
		},
	};
	for (const [pathname, headers] of Object.entries(expected)) {
		assert.deepEqual(serve(pathname).headers, headers, pathname);
	}
});

test("the OAuth callback is the registry's callback page", () => {
	assert.equal(serve("/oauth/callback").file, "/oauth/callback.html");
});

test("plugins.surfsense.com/health answers ok, as the plugin host did", () => {
	const { file } = serve("/health");
	assert.equal(served(file).toString("utf8"), "ok");
});

test("api.surfsense.com/health tells legacy 0.0.x apps to open the sunset page", () => {
	const { file, headers } = serve("/health", "api.surfsense.com");
	assert.equal(headers["content-type"], "application/json");
	assert.equal(headers["cache-control"], "no-store");
	// The archived app reads exactly these two fields, with a 3 s timeout.
	assert.deepEqual(JSON.parse(served(file).toString("utf8")), {
		sunset: true,
		sunset_url: "https://www.surfsense.com/sunset",
	});
});

test("/health on any other host is not rewritten, so it is a 404", () => {
	assert.equal(serve("/health", "example.vercel.app").file, "/health");
});
