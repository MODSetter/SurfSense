export type AgentFilesystemMode = "cloud" | "desktop_local_folder";
export type ClientPlatform = "web" | "desktop";

export interface AgentFilesystemMountSelection {
	mount_id: string;
	root_path: string;
}

export interface AgentFilesystemSelection {
	filesystem_mode: AgentFilesystemMode;
	client_platform: ClientPlatform;
	local_filesystem_mounts?: AgentFilesystemMountSelection[];
}

export interface AgentFilesystemSelectionOptions {
	localFilesystemEnabled: boolean;
}

const DEFAULT_SELECTION: AgentFilesystemSelection = {
	filesystem_mode: "cloud",
	client_platform: "web",
};

export function getClientPlatform(): ClientPlatform {
	if (typeof window === "undefined") return "web";
	return window.electronAPI ? "desktop" : "web";
}

export async function getAgentFilesystemSelection(
	searchSpaceId?: number | null,
	options?: AgentFilesystemSelectionOptions
): Promise<AgentFilesystemSelection> {
	const platform = getClientPlatform();
	if (
		platform !== "desktop" ||
		!options?.localFilesystemEnabled ||
		!window.electronAPI?.getAgentFilesystemSettings
	) {
		return { ...DEFAULT_SELECTION, client_platform: platform };
	}
	try {
		const settings = await window.electronAPI.getAgentFilesystemSettings(searchSpaceId);
		if (settings.mode === "desktop_local_folder") {
			const mounts = await window.electronAPI.getAgentFilesystemMounts?.(searchSpaceId);
			const localFilesystemMounts =
				mounts?.map((entry) => ({
					mount_id: entry.mount,
					root_path: entry.rootPath,
				})) ?? [];
			if (localFilesystemMounts.length === 0) {
				return {
					filesystem_mode: "cloud",
					client_platform: "desktop",
				};
			}
			return {
				filesystem_mode: "desktop_local_folder",
				client_platform: "desktop",
				local_filesystem_mounts: localFilesystemMounts,
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
