/**
 * Tiny glob matcher for exclude patterns.
 *
 * Supports `*` (any chars except `/`), `**` (any chars including `/`), and
 * literal segments. Patterns without a slash are matched against any path
 * segment (so `templates` excludes `templates/foo.md` and `notes/templates/x.md`).
 *
 * Intentionally not a full minimatch — Obsidian users overwhelmingly type
 * folder names ("templates", ".trash") and the obvious wildcards. Avoiding
 * the dependency keeps the bundle small and the mobile attack surface tiny.
 */

const cache = new Map<string, RegExp>();

function compile(pattern: string): RegExp {
	const cached = cache.get(pattern);
	if (cached) return cached;

	let body = "";
	let i = 0;
	while (i < pattern.length) {
		const ch = pattern[i] ?? "";
		if (ch === "*") {
			if (pattern[i + 1] === "*") {
				body += ".*";
				i += 2;
				if (pattern[i] === "/") i += 1;
				continue;
			}
			body += "[^/]*";
			i += 1;
			continue;
		}
		if (".+^${}()|[]\\".includes(ch)) {
			body += "\\" + ch;
			i += 1;
			continue;
		}
		body += ch;
		i += 1;
	}

	const anchored = pattern.includes("/")
		? `^${body}(/.*)?$`
		: `(^|/)${body}(/.*)?$`;
	const re = new RegExp(anchored);
	cache.set(pattern, re);
	return re;
}

export function isExcluded(path: string, patterns: string[]): boolean {
	if (!patterns.length) return false;
	for (const raw of patterns) {
		const trimmed = raw.trim();
		if (!trimmed || trimmed.startsWith("#")) continue;
		if (compile(trimmed).test(path)) return true;
	}
	return false;
}

export function parseExcludePatterns(raw: string): string[] {
	return raw
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => line.length > 0 && !line.startsWith("#"));
}

/** Normalize a folder path: strip leading/trailing slashes; "" or "/" means vault root. */
export function normalizeFolder(folder: string): string {
	return folder.replace(/^\/+|\/+$/g, "");
}

/** True if `path` lives inside `folder` (or `folder` is the vault root). */
export function isInFolder(path: string, folder: string): boolean {
	const f = normalizeFolder(folder);
	if (f === "") return true;
	return path === f || path.startsWith(`${f}/`);
}

/** Exclude wins over include. Empty includeFolders means "include everything". */
export function isFolderFiltered(
	path: string,
	includeFolders: string[],
	excludeFolders: string[],
): boolean {
	for (const f of excludeFolders) {
		if (isInFolder(path, f)) return true;
	}
	if (includeFolders.length === 0) return false;
	for (const f of includeFolders) {
		if (isInFolder(path, f)) return false;
	}
	return true;
}
