import {
	type App,
	type CachedMetadata,
	type FrontMatterCache,
	type HeadingCache,
	type ReferenceCache,
	type TFile,
} from "obsidian";
import type { HeadingRef, NotePayload } from "./types";

/**
 * Build a NotePayload from an Obsidian TFile.
 *
 * Mobile-safety contract:
 *   - No top-level `node:fs` / `node:path` / `node:crypto` imports.
 *     File IO uses `vault.cachedRead` (works on the mobile WASM adapter).
 *     Hashing uses Web Crypto `subtle.digest`.
 *   - Caller MUST first wait for `metadataCache.changed` before calling
 *     this for a `.md` file, otherwise `frontmatter`/`tags`/`headings`
 *     can lag the actual file contents.
 */
export async function buildNotePayload(
	app: App,
	file: TFile,
	vaultId: string,
): Promise<NotePayload> {
	const content = await app.vault.cachedRead(file);
	const cache: CachedMetadata | null = app.metadataCache.getFileCache(file);

	const frontmatter = normalizeFrontmatter(cache?.frontmatter);
	const tags = collectTags(cache);
	const headings = collectHeadings(cache?.headings ?? []);
	const aliases = collectAliases(frontmatter);
	const { embeds, internalLinks } = collectLinks(cache);
	const { resolved, unresolved } = resolveLinkTargets(
		app,
		file.path,
		internalLinks,
	);
	const contentHash = await computeContentHash(content);

	return {
		vault_id: vaultId,
		path: file.path,
		name: file.basename,
		extension: file.extension,
		content,
		frontmatter,
		tags,
		headings,
		resolved_links: resolved,
		unresolved_links: unresolved,
		embeds,
		aliases,
		content_hash: contentHash,
		mtime: file.stat.mtime,
		ctime: file.stat.ctime,
	};
}

export async function computeContentHash(content: string): Promise<string> {
	const bytes = new TextEncoder().encode(content);
	const digest = await crypto.subtle.digest("SHA-256", bytes);
	return bufferToHex(digest);
}

function bufferToHex(buf: ArrayBuffer): string {
	const view = new Uint8Array(buf);
	let hex = "";
	for (let i = 0; i < view.length; i++) {
		hex += (view[i] ?? 0).toString(16).padStart(2, "0");
	}
	return hex;
}

function normalizeFrontmatter(
	fm: FrontMatterCache | undefined,
): Record<string, unknown> {
	if (!fm) return {};
	// FrontMatterCache extends a plain object; strip the `position` key
	// the cache adds so the wire payload stays clean.
	const rest: Record<string, unknown> = { ...(fm as Record<string, unknown>) };
	delete rest.position;
	return rest;
}

function collectTags(cache: CachedMetadata | null): string[] {
	const out = new Set<string>();
	for (const t of cache?.tags ?? []) {
		const tag = t.tag.startsWith("#") ? t.tag.slice(1) : t.tag;
		if (tag) out.add(tag);
	}
	const fmTags: unknown =
		cache?.frontmatter?.tags ?? cache?.frontmatter?.tag;
	if (Array.isArray(fmTags)) {
		for (const t of fmTags) {
			if (typeof t === "string" && t) out.add(t.replace(/^#/, ""));
		}
	} else if (typeof fmTags === "string" && fmTags) {
		for (const t of fmTags.split(/[\s,]+/)) {
			if (t) out.add(t.replace(/^#/, ""));
		}
	}
	return [...out];
}

function collectHeadings(items: HeadingCache[]): HeadingRef[] {
	return items.map((h) => ({ heading: h.heading, level: h.level }));
}

function collectAliases(frontmatter: Record<string, unknown>): string[] {
	const raw = frontmatter.aliases ?? frontmatter.alias;
	if (Array.isArray(raw)) {
		return raw.filter((x): x is string => typeof x === "string" && x.length > 0);
	}
	if (typeof raw === "string" && raw) return [raw];
	return [];
}

function collectLinks(cache: CachedMetadata | null): {
	embeds: string[];
	internalLinks: ReferenceCache[];
} {
	const linkRefs: ReferenceCache[] = [
		...((cache?.links) ?? []),
		...((cache?.embeds as ReferenceCache[] | undefined) ?? []),
	];
	const embeds = ((cache?.embeds as ReferenceCache[] | undefined) ?? []).map(
		(e) => e.link,
	);
	return { embeds, internalLinks: linkRefs };
}

function resolveLinkTargets(
	app: App,
	sourcePath: string,
	links: ReferenceCache[],
): { resolved: string[]; unresolved: string[] } {
	const resolved = new Set<string>();
	const unresolved = new Set<string>();
	for (const link of links) {
		const target = app.metadataCache.getFirstLinkpathDest(
			stripSubpath(link.link),
			sourcePath,
		);
		if (target) {
			resolved.add(target.path);
		} else {
			unresolved.add(link.link);
		}
	}
	return { resolved: [...resolved], unresolved: [...unresolved] };
}

function stripSubpath(link: string): string {
	const hashIdx = link.indexOf("#");
	const pipeIdx = link.indexOf("|");
	let end = link.length;
	if (hashIdx !== -1) end = Math.min(end, hashIdx);
	if (pipeIdx !== -1) end = Math.min(end, pipeIdx);
	return link.slice(0, end);
}
