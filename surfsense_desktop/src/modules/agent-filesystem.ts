import { app, dialog } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";

export type AgentFilesystemMode = "cloud" | "desktop_local_folder";

export interface AgentFilesystemSettings {
	mode: AgentFilesystemMode;
	localRootPath: string | null;
	updatedAt: string;
}

const SETTINGS_FILENAME = "agent-filesystem-settings.json";

function getSettingsPath(): string {
	return join(app.getPath("userData"), SETTINGS_FILENAME);
}

function getDefaultSettings(): AgentFilesystemSettings {
	return {
		mode: "cloud",
		localRootPath: null,
		updatedAt: new Date().toISOString(),
	};
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
			localRootPath: parsed.localRootPath ?? null,
			updatedAt: parsed.updatedAt ?? new Date().toISOString(),
		};
	} catch {
		return getDefaultSettings();
	}
}

export async function setAgentFilesystemSettings(
	settings: Partial<Pick<AgentFilesystemSettings, "mode" | "localRootPath">>
): Promise<AgentFilesystemSettings> {
	const current = await getAgentFilesystemSettings();
	const nextMode =
		settings.mode === "cloud" || settings.mode === "desktop_local_folder"
			? settings.mode
			: current.mode;
	const next: AgentFilesystemSettings = {
		mode: nextMode,
		localRootPath:
			settings.localRootPath === undefined ? current.localRootPath : settings.localRootPath,
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
	if (!settings.localRootPath) {
		throw new Error("No local filesystem root selected");
	}
	return settings.localRootPath;
}

export async function readAgentLocalFileText(
	virtualPath: string
): Promise<{ path: string; content: string }> {
	const rootPath = await resolveCurrentRootPath();
	const absolutePath = resolveVirtualPath(rootPath, virtualPath);
	const content = await readFile(absolutePath, "utf8");
	return {
		path: toVirtualPath(rootPath, absolutePath),
		content,
	};
}

export async function writeAgentLocalFileText(
	virtualPath: string,
	content: string
): Promise<{ path: string }> {
	const rootPath = await resolveCurrentRootPath();
	const absolutePath = resolveVirtualPath(rootPath, virtualPath);
	await mkdir(dirname(absolutePath), { recursive: true });
	await writeFile(absolutePath, content, "utf8");
	return {
		path: toVirtualPath(rootPath, absolutePath),
	};
}
