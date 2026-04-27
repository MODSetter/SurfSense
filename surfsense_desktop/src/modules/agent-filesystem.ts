import { app, dialog } from "electron";
import type { Dirent } from "node:fs";
import { access, mkdir, readdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import { dirname, extname, isAbsolute, join, relative, resolve } from "node:path";

export type AgentFilesystemMode = "cloud" | "desktop_local_folder";

export interface AgentFilesystemSettings {
	mode: AgentFilesystemMode;
	localRootPaths: string[];
	updatedAt: string;
}

type AgentFilesystemSettingsStore = {
	version: 2;
	spaces: Record<string, AgentFilesystemSettings>;
};

const SETTINGS_FILENAME = "agent-filesystem-settings.json";
const MAX_LOCAL_ROOTS = 10;
const DEFAULT_SPACE_KEY = "default";
let cachedSettingsStore: AgentFilesystemSettingsStore | null = null;

const LOCAL_OPENABLE_TEXT_EXTENSIONS = new Set<string>([
	".md",
	".markdown",
	".txt",
	".json",
	".yaml",
	".yml",
	".csv",
	".tsv",
	".xml",
	".html",
	".htm",
	".css",
	".scss",
	".sass",
	".sql",
	".toml",
	".ini",
	".conf",
	".log",
	".py",
	".js",
	".jsx",
	".mjs",
	".cjs",
	".ts",
	".tsx",
	".java",
	".kt",
	".kts",
	".go",
	".rs",
	".rb",
	".php",
	".swift",
	".r",
	".lua",
	".sh",
	".bash",
	".zsh",
	".fish",
	".env",
	".mk",
]);

function getSettingsPath(): string {
	return join(app.getPath("userData"), SETTINGS_FILENAME);
}

function getDefaultSettings(): AgentFilesystemSettings {
	return {
		mode: "cloud",
		localRootPaths: [],
		updatedAt: new Date().toISOString(),
	};
}

async function canonicalizeRootPath(pathValue: string): Promise<string> {
	const resolvedPath = resolve(pathValue);
	try {
		return await realpath(resolvedPath);
	} catch {
		return resolvedPath;
	}
}

function normalizeLocalRootPaths(paths: unknown): string[] {
	if (!Array.isArray(paths)) {
		return [];
	}
	const uniquePaths = new Set<string>();
	for (const rawPath of paths) {
		if (typeof rawPath !== "string") continue;
		const trimmed = rawPath.trim();
		if (!trimmed) continue;
		uniquePaths.add(trimmed);
		if (uniquePaths.size >= MAX_LOCAL_ROOTS) {
			break;
		}
	}
	return [...uniquePaths];
}

async function normalizeLocalRootPathsCanonical(paths: unknown): Promise<string[]> {
	const normalizedPaths = normalizeLocalRootPaths(paths);
	const canonicalizedPaths = await Promise.all(
		normalizedPaths.map((pathValue) => canonicalizeRootPath(pathValue))
	);
	const uniquePaths = new Set<string>();
	for (const canonicalPath of canonicalizedPaths) {
		uniquePaths.add(canonicalPath);
		if (uniquePaths.size >= MAX_LOCAL_ROOTS) {
			break;
		}
	}
	return [...uniquePaths];
}

function normalizeSearchSpaceKey(searchSpaceId?: number | null): string {
	if (typeof searchSpaceId === "number" && Number.isFinite(searchSpaceId) && searchSpaceId > 0) {
		return String(searchSpaceId);
	}
	return DEFAULT_SPACE_KEY;
}

function toSettingsFromUnknown(value: unknown): AgentFilesystemSettings | null {
	if (!value || typeof value !== "object") {
		return null;
	}
	const parsed = value as Partial<AgentFilesystemSettings>;
	if (parsed.mode !== "cloud" && parsed.mode !== "desktop_local_folder") {
		return null;
	}
	return {
		mode: parsed.mode,
		localRootPaths: normalizeLocalRootPaths(parsed.localRootPaths),
		updatedAt: parsed.updatedAt ?? new Date().toISOString(),
	};
}

function getDefaultStore(): AgentFilesystemSettingsStore {
	return { version: 2, spaces: {} };
}

function getSettingsFromStore(
	store: AgentFilesystemSettingsStore,
	searchSpaceId?: number | null
): AgentFilesystemSettings {
	const key = normalizeSearchSpaceKey(searchSpaceId);
	return store.spaces[key] ?? getDefaultSettings();
}

async function loadAgentFilesystemSettingsStore(): Promise<AgentFilesystemSettingsStore> {
	if (cachedSettingsStore) {
		return cachedSettingsStore;
	}
	const settingsPath = getSettingsPath();
	try {
		const raw = await readFile(settingsPath, "utf8");
		const parsed = JSON.parse(raw) as unknown;
		const nextStore = getDefaultStore();
		if (
			parsed &&
			typeof parsed === "object" &&
			"version" in parsed &&
			"spaces" in parsed &&
			(parsed as { version?: unknown }).version === 2
		) {
			const parsedStore = parsed as { spaces?: Record<string, unknown>; version: 2 };
			if (parsedStore.spaces && typeof parsedStore.spaces === "object") {
				for (const [spaceKey, rawSettings] of Object.entries(parsedStore.spaces)) {
					const normalizedSettings = toSettingsFromUnknown(rawSettings);
					if (normalizedSettings) {
						nextStore.spaces[String(spaceKey)] = normalizedSettings;
					}
				}
			}
		} else {
			// Strict migration: reject legacy/non-scoped settings and reset.
			await mkdir(dirname(settingsPath), { recursive: true });
			await writeFile(settingsPath, JSON.stringify(nextStore, null, 2), "utf8");
		}
		cachedSettingsStore = nextStore;
		return nextStore;
	} catch {
		cachedSettingsStore = getDefaultStore();
		await mkdir(dirname(settingsPath), { recursive: true });
		await writeFile(settingsPath, JSON.stringify(cachedSettingsStore, null, 2), "utf8");
		return cachedSettingsStore;
	}
}

export async function getAgentFilesystemSettings(
	searchSpaceId?: number | null
): Promise<AgentFilesystemSettings> {
	const store = await loadAgentFilesystemSettingsStore();
	return getSettingsFromStore(store, searchSpaceId);
}

export async function setAgentFilesystemSettings(
	searchSpaceId: number | null | undefined,
	settings: {
		mode?: AgentFilesystemMode;
		localRootPaths?: string[] | null;
	}
): Promise<AgentFilesystemSettings> {
	const store = await loadAgentFilesystemSettingsStore();
	const key = normalizeSearchSpaceKey(searchSpaceId);
	const current = getSettingsFromStore(store, searchSpaceId);
	const nextMode =
		settings.mode === "cloud" || settings.mode === "desktop_local_folder"
			? settings.mode
			: current.mode;
	const next: AgentFilesystemSettings = {
		mode: nextMode,
		localRootPaths:
			settings.localRootPaths === undefined
				? current.localRootPaths
				: await normalizeLocalRootPathsCanonical(settings.localRootPaths ?? []),
		updatedAt: new Date().toISOString(),
	};

	const settingsPath = getSettingsPath();
	await mkdir(dirname(settingsPath), { recursive: true });
	const nextStore: AgentFilesystemSettingsStore = {
		version: 2,
		spaces: {
			...store.spaces,
			[key]: next,
		},
	};
	await writeFile(settingsPath, JSON.stringify(nextStore, null, 2), "utf8");
	cachedSettingsStore = nextStore;
	return next;
}

export async function pickAgentFilesystemRoot(): Promise<string | null> {
	const result = await dialog.showOpenDialog({
		title: "Select local folder for Agent Filesystem",
		properties: ["openDirectory"],
	});
	if (result.canceled || result.filePaths.length === 0) {
		return null;
	}
	return result.filePaths[0] ?? null;
}

function resolveVirtualPath(rootPath: string, virtualPath: string): string {
	if (!virtualPath.startsWith("/")) {
		throw new Error("Path must start with '/'");
	}
	const normalizedRoot = resolve(rootPath);
	const relativePath = virtualPath.replace(/^\/+/, "");
	if (!relativePath) {
		throw new Error("Path must refer to a file under the selected root");
	}
	const absolutePath = resolve(normalizedRoot, relativePath);
	const rel = relative(normalizedRoot, absolutePath);
	if (!rel || rel.startsWith("..") || isAbsolute(rel)) {
		throw new Error("Path escapes selected local root");
	}
	return absolutePath;
}

function toVirtualPath(rootPath: string, absolutePath: string): string {
	const normalizedRoot = resolve(rootPath);
	const rel = relative(normalizedRoot, absolutePath);
	if (!rel || rel.startsWith("..") || isAbsolute(rel)) {
		return "/";
	}
	return `/${rel.replace(/\\/g, "/")}`;
}

function assertLocalOpenableTextFile(absolutePath: string): void {
	const extension = extname(absolutePath).toLowerCase();
	if (!LOCAL_OPENABLE_TEXT_EXTENSIONS.has(extension)) {
		throw new Error(
			`Unsupported local file type '${extension || "(no extension)"}'. ` +
				"Only text/code files can be opened in local mode."
		);
	}
}

export type LocalRootMount = {
	mount: string;
	rootPath: string;
};

export type AgentFilesystemListOptions = {
	rootPath: string;
	searchSpaceId?: number | null;
	excludePatterns?: string[] | null;
	fileExtensions?: string[] | null;
};

export type AgentFilesystemFileEntry = {
	relativePath: string;
	fullPath: string;
	size: number;
	mtimeMs: number;
};

function sanitizeMountName(rawMount: string): string {
	const normalized = rawMount
		.trim()
		.toLowerCase()
		.replace(/[^a-z0-9_-]+/g, "_")
		.replace(/_+/g, "_")
		.replace(/^[_-]+|[_-]+$/g, "");
	return normalized || "root";
}

function buildRootMounts(rootPaths: string[]): LocalRootMount[] {
	const mounts: LocalRootMount[] = [];
	const usedMounts = new Set<string>();
	for (const rawRootPath of rootPaths) {
		const normalizedRoot = resolve(rawRootPath);
		const baseMount = sanitizeMountName(normalizedRoot.split(/[\\/]/).at(-1) || "root");
		let mount = baseMount;
		let suffix = 2;
		while (usedMounts.has(mount)) {
			mount = `${baseMount}-${suffix}`;
			suffix += 1;
		}
		usedMounts.add(mount);
		mounts.push({ mount, rootPath: normalizedRoot });
	}
	return mounts;
}

export async function getAgentFilesystemMounts(
	searchSpaceId?: number | null
): Promise<LocalRootMount[]> {
	const rootPaths = await resolveCurrentRootPaths(searchSpaceId);
	return buildRootMounts(rootPaths);
}

function normalizeComparablePath(pathValue: string): string {
	const normalized = resolve(pathValue);
	return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}

function normalizeExtensionSet(fileExtensions: string[] | null | undefined): Set<string> | null {
	if (!fileExtensions || fileExtensions.length === 0) {
		return null;
	}
	const set = new Set<string>();
	for (const extension of fileExtensions) {
		if (typeof extension !== "string") continue;
		const trimmed = extension.trim().toLowerCase();
		if (!trimmed) continue;
		set.add(trimmed.startsWith(".") ? trimmed : `.${trimmed}`);
	}
	return set.size > 0 ? set : null;
}

function normalizeExcludeSet(excludePatterns: string[] | null | undefined): Set<string> {
	const set = new Set<string>();
	for (const pattern of excludePatterns ?? []) {
		if (typeof pattern !== "string") continue;
		const trimmed = pattern.trim();
		if (!trimmed) continue;
		set.add(trimmed);
	}
	return set;
}

export async function listAgentFilesystemFiles(
	options: AgentFilesystemListOptions
): Promise<AgentFilesystemFileEntry[]> {
	const allowedRootPaths = await resolveCurrentRootPaths(options.searchSpaceId);
	const requestedRootPath = await canonicalizeRootPath(options.rootPath);
	const normalizedRequestedRoot = normalizeComparablePath(requestedRootPath);
	const allowedRoots = new Set(
		(
			await Promise.all(allowedRootPaths.map((rootPath) => canonicalizeRootPath(rootPath)))
		).map((rootPath) => normalizeComparablePath(rootPath))
	);
	if (!allowedRoots.has(normalizedRequestedRoot)) {
		throw new Error("Selected path is not an allowed local root");
	}

	const excludePatterns = normalizeExcludeSet(options.excludePatterns);
	const extensionSet = normalizeExtensionSet(options.fileExtensions);
	const files: AgentFilesystemFileEntry[] = [];
	const stack: string[] = [requestedRootPath];

	while (stack.length > 0) {
		const currentDir = stack.pop();
		if (!currentDir) continue;
		let entries: Dirent[];
		try {
			entries = await readdir(currentDir, { withFileTypes: true });
		} catch {
			continue;
		}

		for (const entry of entries) {
			if (entry.name.startsWith(".") || excludePatterns.has(entry.name)) {
				continue;
			}
			const absolutePath = join(currentDir, entry.name);
			if (entry.isDirectory()) {
				stack.push(absolutePath);
				continue;
			}
			if (!entry.isFile()) {
				continue;
			}
			if (extensionSet) {
				const extension = extname(entry.name).toLowerCase();
				if (!extensionSet.has(extension)) {
					continue;
				}
			}
			try {
				const fileStat = await stat(absolutePath);
				if (!fileStat.isFile()) {
					continue;
				}
				files.push({
					relativePath: relative(requestedRootPath, absolutePath).replace(/\\/g, "/"),
					fullPath: absolutePath,
					size: fileStat.size,
					mtimeMs: fileStat.mtimeMs,
				});
			} catch {
				// Files can disappear while scanning.
			}
		}
	}

	return files;
}

function parseMountedVirtualPath(
	virtualPath: string,
	mounts: LocalRootMount[]
): {
	mount: string;
	subPath: string;
} {
	if (!virtualPath.startsWith("/")) {
		throw new Error("Path must start with '/'");
	}
	const trimmed = virtualPath.replace(/^\/+/, "");
	if (!trimmed) {
		throw new Error("Path must include a mounted root segment");
	}

	const [mount, ...rest] = trimmed.split("/");
	const remainder = rest.join("/");
	const directMount = mounts.find((entry) => entry.mount === mount);
	if (!directMount) {
		throw new Error(
			`Unknown mounted root '${mount}'. Available roots: ${mounts.map((entry) => `/${entry.mount}`).join(", ")}`
		);
	}
	if (!remainder) {
		throw new Error("Path must include a file path under the mounted root");
	}
	return { mount, subPath: `/${remainder}` };
}

function findMountByName(mounts: LocalRootMount[], mountName: string): LocalRootMount | undefined {
	return mounts.find((entry) => entry.mount === mountName);
}

function toMountedVirtualPath(mount: string, rootPath: string, absolutePath: string): string {
	const relativePath = toVirtualPath(rootPath, absolutePath);
	return `/${mount}${relativePath}`;
}

async function resolveCurrentRootPaths(searchSpaceId?: number | null): Promise<string[]> {
	const settings = await getAgentFilesystemSettings(searchSpaceId);
	if (settings.localRootPaths.length === 0) {
		throw new Error("No local filesystem roots selected");
	}
	return settings.localRootPaths;
}

export async function readAgentLocalFileText(
	virtualPath: string,
	searchSpaceId?: number | null
): Promise<{ path: string; content: string }> {
	const rootPaths = await resolveCurrentRootPaths(searchSpaceId);
	const mounts = buildRootMounts(rootPaths);
	const { mount, subPath } = parseMountedVirtualPath(virtualPath, mounts);
	const rootMount = findMountByName(mounts, mount);
	if (!rootMount) {
		throw new Error(
			`Unknown mounted root '${mount}'. Available roots: ${mounts.map((entry) => `/${entry.mount}`).join(", ")}`
		);
	}
	const absolutePath = resolveVirtualPath(rootMount.rootPath, subPath);
	assertLocalOpenableTextFile(absolutePath);
	const content = await readFile(absolutePath, "utf8");
	return {
		path: toMountedVirtualPath(rootMount.mount, rootMount.rootPath, absolutePath),
		content,
	};
}

export async function writeAgentLocalFileText(
	virtualPath: string,
	content: string,
	searchSpaceId?: number | null
): Promise<{ path: string }> {
	const rootPaths = await resolveCurrentRootPaths(searchSpaceId);
	const mounts = buildRootMounts(rootPaths);
	const { mount, subPath } = parseMountedVirtualPath(virtualPath, mounts);
	const rootMount = findMountByName(mounts, mount);
	if (!rootMount) {
		throw new Error(
			`Unknown mounted root '${mount}'. Available roots: ${mounts.map((entry) => `/${entry.mount}`).join(", ")}`
		);
	}
	let selectedAbsolutePath = resolveVirtualPath(rootMount.rootPath, subPath);

	try {
		await access(selectedAbsolutePath);
	} catch {
		// New files are created under the selected mounted root.
	}
	await mkdir(dirname(selectedAbsolutePath), { recursive: true });
	await writeFile(selectedAbsolutePath, content, "utf8");
	return {
		path: toMountedVirtualPath(rootMount.mount, rootMount.rootPath, selectedAbsolutePath),
	};
}
