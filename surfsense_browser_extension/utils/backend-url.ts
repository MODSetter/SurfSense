import { Storage } from "@plasmohq/storage";

export const BACKEND_URL_STORAGE_KEY = "backend_base_url";
export const FALLBACK_BACKEND_BASE_URL = "https://www.neonote.com";

const storage = new Storage({ area: "local" });

export function normalizeBackendBaseUrl(url: string) {
	return url.trim().replace(/\/+$/, "");
}

export const DEFAULT_BACKEND_BASE_URL = normalizeBackendBaseUrl(
	process.env.PLASMO_PUBLIC_BACKEND_URL || FALLBACK_BACKEND_BASE_URL
);

export async function getCustomBackendBaseUrl() {
	const value = await storage.get(BACKEND_URL_STORAGE_KEY);
	return typeof value === "string" ? normalizeBackendBaseUrl(value) : "";
}

export async function setCustomBackendBaseUrl(url: string) {
	const normalized = normalizeBackendBaseUrl(url);

	if (normalized) {
		await storage.set(BACKEND_URL_STORAGE_KEY, normalized);
		return normalized;
	}

	await storage.remove(BACKEND_URL_STORAGE_KEY);
	return "";
}

export async function getBackendBaseUrl() {
	return (await getCustomBackendBaseUrl()) || DEFAULT_BACKEND_BASE_URL;
}

export async function buildBackendUrl(path: string) {
	const baseUrl = await getBackendBaseUrl();
	const normalizedPath = path.startsWith("/") ? path : `/${path}`;
	return `${baseUrl}${normalizedPath}`;
}
