/**
 * The website's settings from the environment: the license portal's origin and
 * the two announcement switches. NEXT_PUBLIC_* values are baked in at
 * `next build`, so a change needs a redeploy.
 */

// The license portal's origin, https://api.surfsense.com in production. Unset,
// requests stay same-origin relative paths. Not exported: build URLs with
// buildBackendUrl, the one seam for them.
const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "";

type BackendUrlParam = string | number | boolean | null | undefined;

/** A browser-facing URL for `path` on the backend, with `params` as its query; null and undefined are left out. */
export function buildBackendUrl(path: string, params?: Record<string, BackendUrlParam>): string {
	const backendPath = path.startsWith("/") ? path : `/${path}`;
	const queryParams = new URLSearchParams();

	if (params) {
		for (const [key, value] of Object.entries(params)) {
			if (value !== null && value !== undefined) {
				queryParams.append(key, String(value));
			}
		}
	}

	if (BACKEND_URL) {
		const url = new URL(backendPath, BACKEND_URL);
		for (const [key, value] of queryParams) {
			url.searchParams.append(key, value);
		}
		return url.toString();
	}

	const queryString = queryParams.toString();
	if (!queryString) return backendPath;
	return `${backendPath}${backendPath.includes("?") ? "&" : "?"}${queryString}`;
}

// Global announcement banner at the top of every page. Toggle on Vercel via
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED ("true" to show), set the copy with
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_MESSAGE, and the colour with
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_TONE: "info" (default) or "warning".
export const GLOBAL_ANNOUNCEMENT_ENABLED =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED === "true";

export const GLOBAL_ANNOUNCEMENT_MESSAGE =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_MESSAGE ?? "";

export const GLOBAL_ANNOUNCEMENT_TONE: "info" | "warning" =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_TONE === "warning" ? "warning" : "info";

// The announcement pill above the homepage headline, distinct from the banner
// above. Toggle via NEXT_PUBLIC_TOP_ANNOUNCEMENT_ENABLED ("true" to show); the
// name predates the pill, kept so deployments keep working. The copy and link
// are fixed in HomeAnnouncement.
export const TOP_ANNOUNCEMENT_ENABLED = process.env.NEXT_PUBLIC_TOP_ANNOUNCEMENT_ENABLED === "true";
