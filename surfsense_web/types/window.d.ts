import type { PostHog } from "posthog-js";

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
		accessibility: 'authorized' | 'denied' | 'not determined' | 'restricted' | 'limited';
		screenRecording: 'authorized' | 'denied' | 'not determined' | 'restricted' | 'limited';
	}>;
	requestAccessibility: () => Promise<void>;
	requestScreenRecording: () => Promise<void>;
	restartApp: () => Promise<void>;
	// Autocomplete
	onAutocompleteContext: (callback: (data: { screenshot: string; searchSpaceId?: string }) => void) => () => void;
	acceptSuggestion: (text: string) => Promise<void>;
	dismissSuggestion: () => Promise<void>;
	updateSuggestionText: (text: string) => Promise<void>;
	setAutocompleteEnabled: (enabled: boolean) => Promise<void>;
	getAutocompleteEnabled: () => Promise<boolean>;
}

declare global {
	interface Window {
		posthog?: PostHog;
		electronAPI?: ElectronAPI;
	}
}
