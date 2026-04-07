import type { PostHog } from "posthog-js";

interface WatchedFolderConfig {
	path: string;
	name: string;
	excludePatterns: string[];
	fileExtensions: string[] | null;
	rootFolderId: number | null;
	searchSpaceId: number;
	active: boolean;
}

interface FolderSyncFileChangedEvent {
	id: string;
	rootFolderId: number | null;
	searchSpaceId: number;
	folderPath: string;
	folderName: string;
	relativePath: string;
	fullPath: string;
	action: "add" | "change" | "unlink";
	timestamp: number;
}

interface FolderSyncWatcherReadyEvent {
	rootFolderId: number | null;
	folderPath: string;
}

interface LocalFileData {
	name: string;
	data: ArrayBuffer;
	mimeType: string;
	size: number;
}

interface ElectronAPI {
	versions: {
		electron: string;
		node: string;
		chrome: string;
		platform: string;
	};
	openExternal: (url: string) => void;
	getAppVersion: () => Promise<string>;
	onDeepLink: (callback: (url: string) => void) => () => void;
	getQuickAskText: () => Promise<string>;
	setQuickAskMode: (mode: string) => Promise<void>;
	getQuickAskMode: () => Promise<string>;
	replaceText: (text: string) => Promise<void>;
	// Permissions
	getPermissionsStatus: () => Promise<{
		accessibility: "authorized" | "denied" | "not determined" | "restricted" | "limited";
		screenRecording: "authorized" | "denied" | "not determined" | "restricted" | "limited";
	}>;
	requestAccessibility: () => Promise<void>;
	requestScreenRecording: () => Promise<void>;
	restartApp: () => Promise<void>;
	// Autocomplete
	onAutocompleteContext: (
		callback: (data: {
			screenshot: string;
			searchSpaceId?: string;
			appName?: string;
			windowTitle?: string;
		}) => void
	) => () => void;
	acceptSuggestion: (text: string) => Promise<void>;
	dismissSuggestion: () => Promise<void>;
	setAutocompleteEnabled: (enabled: boolean) => Promise<void>;
	getAutocompleteEnabled: () => Promise<boolean>;
	// Folder sync
	selectFolder: () => Promise<string | null>;
	addWatchedFolder: (config: WatchedFolderConfig) => Promise<WatchedFolderConfig[]>;
	removeWatchedFolder: (folderPath: string) => Promise<WatchedFolderConfig[]>;
	getWatchedFolders: () => Promise<WatchedFolderConfig[]>;
	getWatcherStatus: () => Promise<{ path: string; active: boolean; watching: boolean }[]>;
	onFileChanged: (callback: (data: FolderSyncFileChangedEvent) => void) => () => void;
	onWatcherReady: (callback: (data: FolderSyncWatcherReadyEvent) => void) => () => void;
	pauseWatcher: () => Promise<void>;
	resumeWatcher: () => Promise<void>;
	signalRendererReady: () => Promise<void>;
	getPendingFileEvents: () => Promise<FolderSyncFileChangedEvent[]>;
	acknowledgeFileEvents: (eventIds: string[]) => Promise<{ acknowledged: number }>;
	// Browse files/folders via native dialogs
	browseFiles: () => Promise<string[] | null>;
	readLocalFiles: (paths: string[]) => Promise<LocalFileData[]>;
}

declare global {
	interface Window {
		posthog?: PostHog;
		electronAPI?: ElectronAPI;
	}
}
