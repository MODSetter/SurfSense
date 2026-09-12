export const SIDEBAR_COLLAPSED_COOKIE = "sidebar_collapsed";
export const SIDEBAR_WIDTH_COOKIE = "sidebar_width";
export const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export const SIDEBAR_MIN_WIDTH = 240;
export const SIDEBAR_MAX_WIDTH = 480;

export interface SidebarPreferences {
	collapsed: boolean;
	width: number;
}

type SidebarPreferenceCookie = typeof SIDEBAR_COLLAPSED_COOKIE | typeof SIDEBAR_WIDTH_COOKIE;

function setDocumentCookie(name: SidebarPreferenceCookie, value: boolean | number): void {
	try {
		// biome-ignore lint/suspicious/noDocumentCookie: fallback for browsers without Cookie Store API
		document.cookie = `${name}=${value}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}; samesite=lax`;
	} catch {
		// Ignore preference persistence failures.
	}
}

export function persistSidebarPreference(
	name: SidebarPreferenceCookie,
	value: boolean | number
): void {
	if (!window.cookieStore) {
		setDocumentCookie(name, value);
		return;
	}

	void window.cookieStore
		.set({
			name,
			value: String(value),
			path: "/",
			expires: Date.now() + SIDEBAR_COOKIE_MAX_AGE * 1000,
			sameSite: "lax",
		})
		.catch(() => setDocumentCookie(name, value));
}

export function parseSidebarPreferences(
	collapsedValue: string | undefined,
	widthValue: string | undefined
): SidebarPreferences {
	const width = Number(widthValue);

	return {
		collapsed: collapsedValue === "true",
		width:
			Number.isFinite(width) && width >= SIDEBAR_MIN_WIDTH && width <= SIDEBAR_MAX_WIDTH
				? width
				: SIDEBAR_MIN_WIDTH,
	};
}

export function readClientSidebarPreferences(): SidebarPreferences {
	if (typeof document === "undefined") {
		return parseSidebarPreferences(undefined, undefined);
	}

	const cookies = Object.fromEntries(
		document.cookie.split("; ").map((cookie) => {
			const separator = cookie.indexOf("=");
			return separator === -1
				? [cookie, ""]
				: [cookie.slice(0, separator), cookie.slice(separator + 1)];
		})
	);

	return parseSidebarPreferences(cookies[SIDEBAR_COLLAPSED_COOKIE], cookies[SIDEBAR_WIDTH_COOKIE]);
}
