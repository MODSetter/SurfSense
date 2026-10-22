import { APP_VERSION } from "../desktop-dimensions";

const RELEASE_DOWNLOAD = "https://github.com/MODSetter/SurfSense/releases/download";
const RELEASE_FILE = /^SurfSense[-A-Za-z0-9._]*\.(exe|zip|dmg|AppImage|deb)$/;

const SHA512 = /^[A-Za-z0-9+/]{86}==$/;
const BYTE_COUNT = /^[0-9]{1,13}$/;
const ISO_DATE = /^(['"]?)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,3})?Z\1$/;
const PERCENTAGE = /^(100|[1-9]?[0-9])(\.[0-9]+)?$/;

// Every line electron-builder writes for our releases, value shapes included.
// With no YAML parser here, a line outside this list could hide a url (a flow
// mapping, a quoted key, a folded scalar), so it fails the whole manifest and
// the app falls back to GitHub.
const TOP_LEVEL_LINE = /^([A-Za-z][A-Za-z0-9]*):(?: (.*))?$/;
const FILE_START_LINE = /^ {2}- url: (.*)$/;
const FILE_FIELD_LINE = /^ {4}([A-Za-z][A-Za-z0-9]*): (.*)$/;

const TOP_LEVEL_VALUES = new Map<string, RegExp>([
	["version", APP_VERSION],
	["files", /^$/],
	["path", /^\S+$/],
	["sha512", SHA512],
	["releaseDate", ISO_DATE],
	["stagingPercentage", PERCENTAGE],
]);

const FILE_FIELD_VALUES = new Map<string, RegExp>([
	["sha512", SHA512],
	["size", BYTE_COUNT],
	["blockMapSize", BYTE_COUNT],
	["isAdminRightsRequired", /^(true|false)$/],
]);

type Line =
	| { kind: "top"; key: string; value: string }
	| { kind: "file-start"; url: string }
	| { kind: "file-field"; key: string; value: string };

function parseLine(line: string, number: number): Line {
	const fileStart = FILE_START_LINE.exec(line);
	if (fileStart) return { kind: "file-start", url: fileStart[1] };

	const fileField = FILE_FIELD_LINE.exec(line);
	if (fileField && FILE_FIELD_VALUES.get(fileField[1])?.test(fileField[2])) {
		return { kind: "file-field", key: fileField[1], value: fileField[2] };
	}

	const topLevel = TOP_LEVEL_LINE.exec(line);
	const value = topLevel?.[2] ?? "";
	if (topLevel && TOP_LEVEL_VALUES.get(topLevel[1])?.test(value)) {
		return { kind: "top", key: topLevel[1], value };
	}

	throw new Error(`line ${number} is not part of an update manifest`);
}

/** Checks the nesting and that no key repeats, which the app's YAML parser would reject. */
function checkStructure(lines: Line[]): string {
	const topKeys = new Set<string>();
	let inFiles = false;
	let fileKeys: Set<string> | null = null;
	let fileCount = 0;

	for (const line of lines) {
		if (line.kind === "top") {
			if (topKeys.has(line.key)) throw new Error(`${line.key} appears twice`);
			topKeys.add(line.key);
			inFiles = line.key === "files";
			fileKeys = null;
		} else if (line.kind === "file-start") {
			if (!inFiles) throw new Error("a file entry sits outside files:");
			fileKeys = new Set(["url"]);
			fileCount += 1;
		} else {
			if (!fileKeys) throw new Error(`${line.key} sits outside a file entry`);
			if (fileKeys.has(line.key)) throw new Error(`${line.key} appears twice in one file entry`);
			fileKeys.add(line.key);
		}
	}

	const version = lines.find((line) => line.kind === "top" && line.key === "version");
	if (!version || version.kind !== "top") throw new Error("no version");
	if (fileCount === 0) throw new Error("no files");
	return version.value;
}

/** Accepts a bare release file name, or the exact versioned URL for it. */
function releaseFileUrl(value: string, version: string): string {
	const prefix = `${RELEASE_DOWNLOAD}/v${version}/`;
	const name = value.startsWith(prefix) ? value.slice(prefix.length) : value;
	if (!RELEASE_FILE.test(name)) throw new Error("a file is not a SurfSense release file");
	return `${prefix}${name}`;
}

/**
 * Points every url: and path: at the GitHub release for the manifest's own
 * version, leaving hashes, sizes and dates as they are. On Linux the sha512
 * here is the only check on an update, so anything unexpected throws and the
 * route answers 502 rather than serve it (docs/contracts/05-desktop-telemetry.md).
 */
export function pinManifestToRelease(manifest: string): string {
	const body = manifest.endsWith("\n") ? manifest.slice(0, -1) : manifest;
	const lines = body.split("\n").map((line, index) => parseLine(line, index + 1));
	const version = checkStructure(lines);

	const pinned = lines.map((line) => {
		if (line.kind === "file-start") return `  - url: ${releaseFileUrl(line.url, version)}`;
		if (line.kind === "file-field") return `    ${line.key}: ${line.value}`;
		if (line.key === "path") return `path: ${releaseFileUrl(line.value, version)}`;
		return line.value === "" ? `${line.key}:` : `${line.key}: ${line.value}`;
	});
	return `${pinned.join("\n")}\n`;
}
