export const RUNTIME_AUTH_TYPE_COOKIE_NAME = "surfsense_auth_type";

export type RuntimeAuthUiMode = "GOOGLE" | "LOCAL";

export function resolveRuntimeAuthUiMode(
	value: string | null | undefined,
	fallback: string | null | undefined = "LOCAL"
): RuntimeAuthUiMode {
	const candidate = value?.trim().toUpperCase();
	if (candidate === "GOOGLE") return "GOOGLE";
	if (candidate === "LOCAL") return "LOCAL";

	const fallbackCandidate = fallback?.trim().toUpperCase();
	return fallbackCandidate === "GOOGLE" ? "GOOGLE" : "LOCAL";
}

export function getRuntimeAuthInitScript(fallbackAuthType: string): string {
	const fallback = resolveRuntimeAuthUiMode(fallbackAuthType);
	const cookieName = JSON.stringify(RUNTIME_AUTH_TYPE_COOKIE_NAME);
	const fallbackValue = JSON.stringify(fallback);

	return `
(function() {
	try {
		var cookieName = ${cookieName};
		var fallback = ${fallbackValue};
		var prefix = cookieName + "=";
		var rawValue = fallback;
		var cookies = document.cookie ? document.cookie.split(";") : [];
		for (var i = 0; i < cookies.length; i++) {
			var cookie = cookies[i].trim();
			if (cookie.indexOf(prefix) === 0) {
				rawValue = decodeURIComponent(cookie.slice(prefix.length));
				break;
			}
		}
		var normalized = String(rawValue || fallback).toUpperCase() === "GOOGLE" ? "GOOGLE" : "LOCAL";
		window.__SURFSENSE_AUTH_TYPE__ = normalized;
		document.documentElement.setAttribute("data-surfsense-auth-type", normalized);
	} catch (_) {
		window.__SURFSENSE_AUTH_TYPE__ = ${fallbackValue};
		document.documentElement.setAttribute("data-surfsense-auth-type", ${fallbackValue});
	}
})();
`;
}

declare global {
	interface Window {
		__SURFSENSE_AUTH_TYPE__?: RuntimeAuthUiMode;
	}
}
