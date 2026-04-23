import { app, dialog } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

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
