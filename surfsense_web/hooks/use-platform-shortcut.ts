import { useCallback, useEffect, useState } from "react";

interface NavigatorUAData {
	platform: string;
}

function getIsMac() {
	if (typeof navigator === "undefined") return false;

	// Modern API (Chromium browsers: Chrome, Edge, Opera)
	const uaData = (navigator as Navigator & { userAgentData?: NavigatorUAData }).userAgentData;
	if (uaData?.platform) {
		return uaData.platform === "macOS";
	}

	// Fallback for Firefox/Safari
	return /Mac|iPhone/.test(navigator.platform);
}

/**
 * Returns a helper that formats keyboard shortcut strings with
 * platform-aware modifier symbols.
 *
 * SSR-safe: returns an empty string until mounted so there is no hydration
 * mismatch.
 */
export function usePlatformShortcut() {
	const [ready, setReady] = useState(false);
	const [isMac, setIsMac] = useState(false);

	useEffect(() => {
		setIsMac(getIsMac());
		setReady(true);
	}, []);

	const shortcut = useCallback(
		(...keys: string[]) => {
			if (!ready) return "";

			const mod = isMac ? "⌘" : "Ctrl";
			const shift = isMac ? "⇧" : "Shift";
			const alt = isMac ? "⌥" : "Alt";

			const mapped = keys.map((k) => {
				if (k === "Mod") return mod;
				if (k === "Shift") return shift;
				if (k === "Alt") return alt;
				return k;
			});

			return `(${mapped.join("+")})`;
		},
		[ready, isMac]
	);

	return { shortcut, isMac, ready };
}
