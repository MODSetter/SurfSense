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
}

declare global {
	interface Window {
		posthog?: PostHog;
		electronAPI?: ElectronAPI;
	}
}
