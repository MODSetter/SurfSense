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

interface FolderFileEntry {
	relativePath: string;
	fullPath: string;
	size: number;
	mtimeMs: number;
}

type AgentFilesystemMode = "cloud" | "desktop_local_folder";

interface AgentFilesystemSettings {
	mode: AgentFilesystemMode;
	localRootPaths: string[];
	updatedAt: string;
}

interface AgentFilesystemMount {
	mount: string;
	rootPath: string;
}

interface AgentFilesystemListOptions {
	rootPath: string;
	searchSpaceId?: number | null;
	excludePatterns?: string[] | null;
	fileExtensions?: string[] | null;
}

interface AgentFilesystemTreeWatchOptions {
	searchSpaceId?: number | null;
	rootPaths: string[];
	excludePatterns?: string[] | null;
	fileExtensions?: string[] | null;
}

interface AgentFilesystemTreeDirtyEvent {
	searchSpaceId: number | null;
	reason: "watcher_event" | "safety_poll";
	rootPath: string;
	changedPath: string | null;
	timestamp: number;
}

interface LocalTextFileResult {
	ok: boolean;
	path: string;
	content?: string;
	error?: string;
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
	onChatScreenCapture: (callback: (dataUrl: string) => void) => () => void;
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
	captureFullScreen: () => Promise<string | null>;
	restartApp: () => Promise<void>;
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
	listFolderFiles: (config: WatchedFolderConfig) => Promise<FolderFileEntry[]>;
	seedFolderMtimes: (folderPath: string, mtimes: Record<string, number>) => Promise<void>;
	// Browse files/folders via native dialogs
	browseFiles: () => Promise<string[] | null>;
	readLocalFiles: (paths: string[]) => Promise<LocalFileData[]>;
	readAgentLocalFileText: (
		virtualPath: string,
		searchSpaceId?: number | null
	) => Promise<LocalTextFileResult>;
	writeAgentLocalFileText: (
		virtualPath: string,
		content: string,
		searchSpaceId?: number | null
	) => Promise<LocalTextFileResult>;
	// Auth token sync across windows
	getAuthTokens: () => Promise<{ bearer: string; refresh: string } | null>;
	setAuthTokens: (bearer: string, refresh: string) => Promise<void>;
	// Keyboard shortcut configuration
	getShortcuts: () => Promise<{
		generalAssist: string;
		quickAsk: string;
		screenshotAssist: string;
	}>;
	setShortcuts: (
		config: Partial<{ generalAssist: string; quickAsk: string; screenshotAssist: string }>
	) => Promise<{
		generalAssist: string;
		quickAsk: string;
		screenshotAssist: string;
	}>;
	// Launch on system startup
	getAutoLaunch: () => Promise<{
		enabled: boolean;
		openAsHidden: boolean;
		supported: boolean;
	}>;
	setAutoLaunch: (
		enabled: boolean,
		openAsHidden?: boolean
	) => Promise<{ enabled: boolean; openAsHidden: boolean; supported: boolean }>;
	// Active search space
	getActiveSearchSpace: () => Promise<string | null>;
	setActiveSearchSpace: (id: string) => Promise<void>;
	// Analytics bridge (PostHog mirror into the Electron main process)
	analyticsIdentify: (userId: string, properties?: Record<string, unknown>) => Promise<void>;
	analyticsReset: () => Promise<void>;
	analyticsCapture: (event: string, properties?: Record<string, unknown>) => Promise<void>;
	getAnalyticsContext: () => Promise<{
		distinctId: string;
		machineId: string;
		appVersion: string;
		platform: string;
	}>;
	// Agent filesystem mode
	getAgentFilesystemSettings: (searchSpaceId?: number | null) => Promise<AgentFilesystemSettings>;
	getAgentFilesystemMounts: (searchSpaceId?: number | null) => Promise<AgentFilesystemMount[]>;
	listAgentFilesystemFiles: (options: AgentFilesystemListOptions) => Promise<FolderFileEntry[]>;
	startAgentFilesystemTreeWatch: (
		options: AgentFilesystemTreeWatchOptions
	) => Promise<{ ok: true }>;
	stopAgentFilesystemTreeWatch: (searchSpaceId?: number | null) => Promise<{ ok: true }>;
	onAgentFilesystemTreeDirty: (
		callback: (data: AgentFilesystemTreeDirtyEvent) => void
	) => () => void;
	setAgentFilesystemSettings: (
		settings: {
			mode?: AgentFilesystemMode;
			localRootPaths?: string[] | null;
		},
		searchSpaceId?: number | null
	) => Promise<AgentFilesystemSettings>;
	pickAgentFilesystemRoot: () => Promise<string | null>;
}

declare global {
	interface Window {
		posthog?: PostHog;
		electronAPI?: ElectronAPI;
	}
}
