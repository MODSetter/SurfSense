/**
 * The license portal's origin from the environment. NEXT_PUBLIC_* values are
 * baked in at `next build`, so a change needs a redeploy.
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
