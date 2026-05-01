/**
 * Runtime environment variable substitution for Next.js Docker images.
 *
 * Next.js inlines NEXT_PUBLIC_* values at build time. The Docker image is built
 * with unique placeholder strings (e.g. __NEXT_PUBLIC_FASTAPI_BACKEND_URL__).
 * This script replaces those placeholders with real values from the container's
 * environment variables before the server starts.
 *
 * Runs once at container startup via docker-entrypoint.sh.
 */

const fs = require("fs");
const path = require("path");

const replacements = [
	[
		"__NEXT_PUBLIC_FASTAPI_BACKEND_URL__",
		process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000",
	],
	[
		"__NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__",
		process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "LOCAL",
	],
	["__NEXT_PUBLIC_ETL_SERVICE__", process.env.NEXT_PUBLIC_ETL_SERVICE || "DOCLING"],
	[
		"__NEXT_PUBLIC_ZERO_CACHE_URL__",
		process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848",
	],
	["__NEXT_PUBLIC_DEPLOYMENT_MODE__", process.env.NEXT_PUBLIC_DEPLOYMENT_MODE || "self-hosted"],
	["__NEXT_PUBLIC_OAUTH2_PROXY_URL__", process.env.NEXT_PUBLIC_OAUTH2_PROXY_URL || ""],
	[
		"__NEXT_PUBLIC_SMB_NAME__",
		(process.env.SMB_NAME || process.env.NEXT_PUBLIC_SMB_NAME || "moneta").trim() || "moneta",
	],
];

let filesProcessed = 0;
let filesModified = 0;

function walk(dir) {
	let entries;
	try {
		entries = fs.readdirSync(dir, { withFileTypes: true });
	} catch {
		return;
	}
	for (const entry of entries) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			walk(full);
		} else if (entry.name.endsWith(".js")) {
			filesProcessed++;
			let content = fs.readFileSync(full, "utf8");
			let changed = false;
			for (const [placeholder, value] of replacements) {
				if (content.includes(placeholder)) {
					content = content.replaceAll(placeholder, value);
					changed = true;
				}
			}
			if (changed) {
				fs.writeFileSync(full, content);
				filesModified++;
			}
		}
	}
}

console.log("[entrypoint] Replacing environment variable placeholders...");
for (const [placeholder, value] of replacements) {
	console.log(`  ${placeholder} -> ${value}`);
}

walk(path.join(__dirname, ".next"));

const serverJs = path.join(__dirname, "server.js");
if (fs.existsSync(serverJs)) {
	let content = fs.readFileSync(serverJs, "utf8");
	let changed = false;
	filesProcessed++;
	for (const [placeholder, value] of replacements) {
		if (content.includes(placeholder)) {
			content = content.replaceAll(placeholder, value);
			changed = true;
		}
	}
	if (changed) {
		fs.writeFileSync(serverJs, content);
		filesModified++;
	}
}

console.log(`[entrypoint] Done. Scanned ${filesProcessed} files, modified ${filesModified}.`);
