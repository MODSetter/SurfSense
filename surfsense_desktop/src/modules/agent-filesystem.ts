import { app, dialog } from "electron";
import { access, mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";

export type AgentFilesystemMode = "cloud" | "desktop_local_folder";

export interface AgentFilesystemSettings {
	mode: AgentFilesystemMode;
	localRootPaths: string[];
	updatedAt: string;
}

const SETTINGS_FILENAME = "agent-filesystem-settings.json";
const MAX_LOCAL_ROOTS = 5;

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

async function normalizeLocalRootPaths(paths: unknown): Promise<string[]> {
	if (!Array.isArray(paths)) {
		return [];
	}
	const uniquePaths = new Set<string>();
	for (const rawPath of paths) {
		if (typeof rawPath !== "string") continue;
		const trimmed = rawPath.trim();
		if (!trimmed) continue;
		const canonicalRootPath = await canonicalizeRootPath(trimmed);
		uniquePaths.add(canonicalRootPath);
		if (uniquePaths.size >= MAX_LOCAL_ROOTS) {
			break;
		}
	}
	return [...uniquePaths];
}

export async function getAgentFilesystemSettings(): Promise<AgentFilesystemSettings> {
	try {
		const raw = await readFile(getSettingsPath(), "utf8");
		const parsed = JSON.parse(raw) as Partial<AgentFilesystemSettings>;
		if (parsed.mode !== "cloud" && parsed.mode !== "desktop_local_folder") {
			return getDefaultSettings();
		}
		return {
			mode: parsed.mode,
			localRootPaths: await normalizeLocalRootPaths(parsed.localRootPaths),
			updatedAt: parsed.updatedAt ?? new Date().toISOString(),
		};
	} catch {
		return getDefaultSettings();
	}
}

export async function setAgentFilesystemSettings(
	settings: {
		mode?: AgentFilesystemMode;
		localRootPaths?: string[] | null;
	}
): Promise<AgentFilesystemSettings> {
	const current = await getAgentFilesystemSettings();
	const nextMode =
		settings.mode === "cloud" || settings.mode === "desktop_local_folder"
			? settings.mode
			: current.mode;
	const next: AgentFilesystemSettings = {
		mode: nextMode,
		localRootPaths:
			settings.localRootPaths === undefined
				? current.localRootPaths
				: await normalizeLocalRootPaths(settings.localRootPaths ?? []),
		updatedAt: new Date().toISOString(),
	};

	const settingsPath = getSettingsPath();
	await mkdir(dirname(settingsPath), { recursive: true });
	await writeFile(settingsPath, JSON.stringify(next, null, 2), "utf8");
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

export type LocalRootMount = {
	mount: string;
	rootPath: string;
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

export async function getAgentFilesystemMounts(): Promise<LocalRootMount[]> {
	const rootPaths = await resolveCurrentRootPaths();
	return buildRootMounts(rootPaths);
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

async function resolveCurrentRootPaths(): Promise<string[]> {
	const settings = await getAgentFilesystemSettings();
	if (settings.localRootPaths.length === 0) {
		throw new Error("No local filesystem roots selected");
	}
	return settings.localRootPaths;
}

export async function readAgentLocalFileText(
	virtualPath: string
): Promise<{ path: string; content: string }> {
	const rootPaths = await resolveCurrentRootPaths();
	const mounts = buildRootMounts(rootPaths);
	const { mount, subPath } = parseMountedVirtualPath(virtualPath, mounts);
	const rootMount = findMountByName(mounts, mount);
	if (!rootMount) {
		throw new Error(
			`Unknown mounted root '${mount}'. Available roots: ${mounts.map((entry) => `/${entry.mount}`).join(", ")}`
		);
	}
	const absolutePath = resolveVirtualPath(rootMount.rootPath, subPath);
	const content = await readFile(absolutePath, "utf8");
	return {
		path: toMountedVirtualPath(rootMount.mount, rootMount.rootPath, absolutePath),
		content,
	};
}

export async function writeAgentLocalFileText(
	virtualPath: string,
	content: string
): Promise<{ path: string }> {
	const rootPaths = await resolveCurrentRootPaths();
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
