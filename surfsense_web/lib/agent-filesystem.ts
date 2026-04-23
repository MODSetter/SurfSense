export type AgentFilesystemMode = "cloud" | "desktop_local_folder";
export type ClientPlatform = "web" | "desktop";

export interface AgentFilesystemSelection {
	filesystem_mode: AgentFilesystemMode;
	client_platform: ClientPlatform;
	local_filesystem_roots?: string[];
}

const DEFAULT_SELECTION: AgentFilesystemSelection = {
	filesystem_mode: "cloud",
	client_platform: "web",
};

export function getClientPlatform(): ClientPlatform {
	if (typeof window === "undefined") return "web";
	return window.electronAPI ? "desktop" : "web";
}

export async function getAgentFilesystemSelection(): Promise<AgentFilesystemSelection> {
	const platform = getClientPlatform();
	if (platform !== "desktop" || !window.electronAPI?.getAgentFilesystemSettings) {
		return { ...DEFAULT_SELECTION, client_platform: platform };
	}
	try {
		const settings = await window.electronAPI.getAgentFilesystemSettings();
		const firstLocalRootPath = settings.localRootPaths[0];
		if (settings.mode === "desktop_local_folder" && firstLocalRootPath) {
			return {
				filesystem_mode: "desktop_local_folder",
				client_platform: "desktop",
				local_filesystem_roots: settings.localRootPaths,
			};
		}
		return {
			filesystem_mode: "cloud",
			client_platform: "desktop",
		};
	} catch {
		return {
			filesystem_mode: "cloud",
			client_platform: "desktop",
		};
	}
}
