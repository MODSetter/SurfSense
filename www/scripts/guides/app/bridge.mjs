/**
 * What Electron's preload gives the renderer, for a renderer in a plain browser.
 *
 * Only `apiUrl` is required (`frontend/src/lib/api.ts`); the rest makes the page
 * look as it does in the app: without `updates` Settings is a row short, and
 * without `privacy` setup skips its privacy step. Opening files and links does
 * nothing, since a capture has no desktop to open them on.
 *
 * Runs in the page through `addInitScript`, so it must not close over anything.
 */
export function installBridge({
	apiUrl,
	version,
	firstRunAsked,
	updatesAutomatic = false,
	usageStatistics = null,
}) {
	const listeners = new Set();
	let privacy = {
		updates: {
			automatic: updatesAutomatic,
			locked: false,
			lockedReason: null,
			channel: null,
			host: "updates.surfsense.com",
			fallbackHost: "github.com",
			lastCheckedAt: null,
			lastRequest: null,
		},
		usageStatistics: {
			enabled: firstRunAsked ? Boolean(usageStatistics) : null,
			locked: false,
			lockedReason: null,
			host: "us.i.posthog.com",
			lastSent: null,
		},
		firstRunAsked,
	};
	const publish = (next) => {
		privacy = next;
		for (const listener of listeners) listener(privacy);
	};
	const nothing = async () => {};
	const noListener = () => () => {};
	const updateState = {
		current: { status: "idle" },
		checkedAt: undefined,
		listeners: new Set(),
		set(next) {
			this.current = next;
			for (const listener of this.listeners) listener(next);
		},
	};

	window.surfsense = {
		apiUrl,
		platform: "win32",
		databaseIdentity: () => "guides",
		openDocument: async () => "",
		revealDocument: async () => "",
		// A check answers as the updater does when this is the newest version: checking, then up to date.
		updates: {
			prefs: async () => ({
				automatic: privacy.updates.automatic,
				lastCheckedAt: updateState.checkedAt,
			}),
			setAutomatic: async (automatic) => ({ automatic }),
			state: async () => updateState.current,
			check: async () => {
				updateState.set({ status: "checking" });
				await new Promise((resolve) => setTimeout(resolve, 1200));
				updateState.checkedAt = new Date().toISOString();
				updateState.set({ status: "up-to-date" });
			},
			install: nothing,
			onState: (listener) => {
				updateState.listeners.add(listener);
				return () => updateState.listeners.delete(listener);
			},
			onCheckRequested: noListener,
		},
		privacy: {
			getState: async () => privacy,
			setUsageStatistics: async (enabled) =>
				publish({ ...privacy, usageStatistics: { ...privacy.usageStatistics, enabled } }),
			setUpdatesAutomatic: async (automatic) =>
				publish({ ...privacy, updates: { ...privacy.updates, automatic } }),
			previewUsageReport: async () => null,
			completeFirstRun: async (choices) =>
				publish({
					...privacy,
					firstRunAsked: true,
					updates: { ...privacy.updates, automatic: choices.updates },
					usageStatistics: { ...privacy.usageStatistics, enabled: choices.usageStatistics },
				}),
			onStateChanged: (listener) => {
				listeners.add(listener);
				return () => listeners.delete(listener);
			},
		},
		openExternal: nothing,
		openConfirmedLink: nothing,
		openPluginPage: nothing,
		about: {
			details: async () => ({
				version,
				electron: "",
				chrome: "",
				node: "",
				os: "Windows 11",
				arch: "x64",
			}),
		},
		microphone: {
			status: async () => "granted",
			request: async () => "granted",
			openSettings: async () => true,
		},
		sidecars: { onCrash: noListener },
		help: { onReportIssue: noListener },
	};
}
