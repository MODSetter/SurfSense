import { app, dialog } from "electron";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
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

function normalizeLocalRootPaths(paths: unknown): string[] {
	if (!Array.isArray(paths)) {
		return [];
	}
	const uniquePaths = new Set<string>();
	for (const path of paths) {
		if (typeof path !== "string") continue;
		const trimmed = path.trim();
		if (!trimmed) continue;
		uniquePaths.add(trimmed);
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
			localRootPaths: normalizeLocalRootPaths(parsed.localRootPaths),
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
				: normalizeLocalRootPaths(settings.localRootPaths ?? []),
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

async function resolveCurrentRootPath(): Promise<string> {
	const settings = await getAgentFilesystemSettings();
	if (settings.localRootPaths.length === 0) {
		throw new Error("No local filesystem roots selected");
	}
	return settings.localRootPaths[0];
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
	for (const rootPath of rootPaths) {
		const absolutePath = resolveVirtualPath(rootPath, virtualPath);
		try {
			const content = await readFile(absolutePath, "utf8");
			return {
				path: toVirtualPath(rootPath, absolutePath),
				content,
			};
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code === "ENOENT") {
				continue;
			}
			throw error;
		}
	}
	// Keep the same relative virtual path in the error context.
	const fallbackRootPath = await resolveCurrentRootPath();
	const fallbackAbsolutePath = resolveVirtualPath(fallbackRootPath, virtualPath);
	const content = await readFile(fallbackAbsolutePath, "utf8");
	return {
		path: toVirtualPath(fallbackRootPath, fallbackAbsolutePath),
		content,
	};
}

export async function writeAgentLocalFileText(
	virtualPath: string,
	content: string
): Promise<{ path: string }> {
	const rootPaths = await resolveCurrentRootPaths();
	let selectedRootPath = rootPaths[0];
	let selectedAbsolutePath = resolveVirtualPath(selectedRootPath, virtualPath);

	for (const rootPath of rootPaths) {
		const absolutePath = resolveVirtualPath(rootPath, virtualPath);
		try {
			await access(absolutePath);
			selectedRootPath = rootPath;
			selectedAbsolutePath = absolutePath;
			break;
		} catch {
			// Keep searching for an existing file path across selected roots.
		}
	}

	await mkdir(dirname(selectedAbsolutePath), { recursive: true });
	await writeFile(selectedAbsolutePath, content, "utf8");
	return {
		path: toVirtualPath(selectedRootPath, selectedAbsolutePath),
	};
}
