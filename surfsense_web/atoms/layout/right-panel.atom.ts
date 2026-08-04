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
		document.cookie = `${RIGHT_PANEL_COLLAPSED_COOKIE}=${value}; path=/; max-age=${RIGHT_PANEL_COOKIE_MAX_AGE}; samesite=lax`;
	},
	removeItem: () => {
		document.cookie = `${RIGHT_PANEL_COLLAPSED_COOKIE}=; path=/; max-age=0; samesite=lax`;
	},
};

export type RightPanelTab =
	| "sources"
	| "report"
	| "editor"
	| "hitl-edit"
	| "citation"
	| "artifacts";

export const rightPanelTabAtom = atom<RightPanelTab>("sources");

/** Whether the right panel is collapsed (hidden but state preserved) */
export const rightPanelCollapsedAtom = atomWithStorage(
	RIGHT_PANEL_COLLAPSED_COOKIE,
	false,
	rightPanelCookieStorage,
	{ getOnInit: true }
);
