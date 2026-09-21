import { useEffect, useMemo, useState } from "react";
import type { ReleaseAsset } from "@/lib/app-release";
import { APP_RELEASE_TAG } from "@/lib/app-release";

export {
	ASSET_LABELS,
	GITHUB_RELEASES_URL,
	getAssetLabel,
	type ReleaseAsset,
} from "@/lib/app-release";

export type OSInfo = {
	os: "macOS" | "Windows" | "Linux" | "Android" | "iOS";
	arch: "arm64" | "x64";
};

export function useUserOS(): OSInfo {
	const [info, setInfo] = useState<OSInfo>({ os: "macOS", arch: "arm64" });
	useEffect(() => {
		const ua = navigator.userAgent;
		let os: OSInfo["os"] = "macOS";
		let arch: OSInfo["arch"] = "x64";

		if (/Android/i.test(ua)) {
			os = "Android";
			arch = "arm64";
		} else if (/iPhone|iPad|iPod/i.test(ua)) {
			os = "iOS";
			arch = "arm64";
		} else if (/Windows/i.test(ua)) {
			os = "Windows";
			arch = "x64";
		} else if (/Linux/i.test(ua)) {
			os = "Linux";
			arch = "x64";
		} else {
			os = "macOS";
			arch = /Mac/.test(ua) && !/Intel/.test(ua) ? "arm64" : "arm64";
		}

		const uaData = (navigator as Navigator & { userAgentData?: { architecture?: string } })
			.userAgentData;
		if (uaData?.architecture === "arm") arch = "arm64";
		else if (uaData?.architecture === "x86") arch = "x64";

		setInfo({ os, arch });
	}, []);
	return info;
}

/**
 * Resolved by tag, so a deployed page offers the build it was built against
 * rather than whatever shipped since. Server-rendered pages should use
 * `getReleaseAssets()` in `lib/release-assets.ts` instead of this hook.
 */
export function useLatestRelease() {
	const [assets, setAssets] = useState<ReleaseAsset[]>([]);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		const controller = new AbortController();
		fetch(`https://api.github.com/repos/MODSetter/SurfSense/releases/tags/${APP_RELEASE_TAG}`, {
			signal: controller.signal,
		})
			.then((r) => r.json())
			.then((data) => {
				if (data?.assets) {
					setAssets(
						data.assets
							.filter((a: { name: string }) => /\.(exe|dmg|AppImage|deb)$/.test(a.name))
							.map((a: { name: string; browser_download_url: string }) => ({
								name: a.name,
								url: a.browser_download_url,
							}))
					);
				}
			})
			.catch(() => {})
			.finally(() => setIsLoading(false));
		return () => controller.abort();
	}, []);

	return { assets, isLoading };
}

export function usePrimaryDownload() {
	const { os, arch } = useUserOS();
	const { assets, isLoading } = useLatestRelease();
	const isMobileOS = os === "Android" || os === "iOS";

	const { primary, alternatives } = useMemo(() => {
		if (assets.length === 0) return { primary: null, alternatives: [] };
		if (isMobileOS) return { primary: null, alternatives: assets };

		const matchers: Record<string, (n: string) => boolean> = {
			Windows: (n) => n.endsWith(".exe"),
			macOS: (n) => n.endsWith(`-${arch}.dmg`),
			Linux: (n) => n.endsWith(".AppImage"),
		};

		const match = matchers[os];
		const primary = assets.find((a) => match(a.name)) ?? null;
		const alternatives = assets.filter((a) => a !== primary);
		return { primary, alternatives };
	}, [assets, os, arch, isMobileOS]);

	return { os, arch, assets, primary, alternatives, isMobileOS, isLoading };
}
