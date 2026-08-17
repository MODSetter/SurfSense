import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

const RIGHT_PANEL_COLLAPSED_COOKIE = "surfsense_right_panel_collapsed";
const RIGHT_PANEL_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const rightPanelCookieStorage = {
	getItem: (_key: string, initialValue: boolean) => {
		if (typeof document === "undefined") return initialValue;
		const match = document.cookie.match(/(?:^|; )surfsense_right_panel_collapsed=([^;]+)/);
		return match ? match[1] === "true" : initialValue;
	},
	setItem: (_key: string, value: boolean) => {
		void window.cookieStore
			?.set({
				name: RIGHT_PANEL_COLLAPSED_COOKIE,
				value: String(value),
				path: "/",
				expires: Date.now() + RIGHT_PANEL_COOKIE_MAX_AGE * 1000,
				sameSite: "lax",
			})
			.catch(() => {
				// Ignore preference persistence failures.
			});
	},
	removeItem: () => {
		void window.cookieStore
			?.delete({
				name: RIGHT_PANEL_COLLAPSED_COOKIE,
				path: "/",
			})
			.catch(() => {
				// Ignore preference persistence failures.
			});
	},
};

export type RightPanelTab =
	| "sources"
	| "artifact"
	| "editor"
	| "hitl-edit"
	| "citation"
	| "artifacts"
	| "document";

export const rightPanelTabAtom = atom<RightPanelTab>("sources");

/** Whether the right panel is collapsed (hidden but state preserved) */
export const rightPanelCollapsedAtom = atomWithStorage(
	RIGHT_PANEL_COLLAPSED_COOKIE,
	false,
	rightPanelCookieStorage,
	{ getOnInit: true }
);
