import { useEffect, useMemo, useState } from "react";

export type OSInfo = {
	os: "macOS" | "Windows" | "Linux";
	arch: "arm64" | "x64";
};

export function useUserOS(): OSInfo {
	const [info, setInfo] = useState<OSInfo>({ os: "macOS", arch: "arm64" });
	useEffect(() => {
		const ua = navigator.userAgent;
		let os: OSInfo["os"] = "macOS";
		let arch: OSInfo["arch"] = "x64";

		if (/Windows/i.test(ua)) {
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

export interface ReleaseAsset {
	name: string;
	url: string;
}

export function useLatestRelease() {
	const [assets, setAssets] = useState<ReleaseAsset[]>([]);

	useEffect(() => {
		const controller = new AbortController();
		fetch("https://api.github.com/repos/MODSetter/SurfSense/releases/latest", {
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
			.catch(() => {});
		return () => controller.abort();
	}, []);

	return assets;
}

export const ASSET_LABELS: Record<string, string> = {
	".exe": "Windows (exe)",
	"-arm64.dmg": "macOS Apple Silicon (dmg)",
	"-x64.dmg": "macOS Intel (dmg)",
	"-arm64.zip": "macOS Apple Silicon (zip)",
	"-x64.zip": "macOS Intel (zip)",
	".AppImage": "Linux (AppImage)",
	".deb": "Linux (deb)",
};

export function getAssetLabel(name: string): string {
	for (const [suffix, label] of Object.entries(ASSET_LABELS)) {
		if (name.endsWith(suffix)) return label;
	}
	return name;
}

export const GITHUB_RELEASES_URL = "https://github.com/MODSetter/SurfSense/releases/latest";

export function usePrimaryDownload() {
	const { os, arch } = useUserOS();
	const assets = useLatestRelease();

	const { primary, alternatives } = useMemo(() => {
		if (assets.length === 0) return { primary: null, alternatives: [] };

		const matchers: Record<string, (n: string) => boolean> = {
			Windows: (n) => n.endsWith(".exe"),
			macOS: (n) => n.endsWith(`-${arch}.dmg`),
			Linux: (n) => n.endsWith(".AppImage"),
		};

		const match = matchers[os];
		const primary = assets.find((a) => match(a.name)) ?? null;
		const alternatives = assets.filter((a) => a !== primary);
		return { primary, alternatives };
	}, [assets, os, arch]);

	return { os, arch, assets, primary, alternatives };
}
