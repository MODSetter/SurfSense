"use client";

import { FlowButton } from "@/components/ui/flow-button";
import { DownloadIcon } from "@/components/ui/icons";
import {
	ASSET_LABELS,
	GITHUB_RELEASES_URL,
	getAssetLabel,
	useLatestRelease,
	usePrimaryDownload,
} from "@/lib/desktop-download-utils";

/**
 * The two pieces of `lib/desktop-download-utils.ts` this page needs, split
 * into client components so `page.tsx` can stay a server component: the
 * hero's single auto-detected button, and the three-way OS grid below it.
 */

export function PrimaryDownloadButton() {
	const { os, primary, isMobileOS, isLoading } = usePrimaryDownload();

	if (isMobileOS) {
		return (
			<p className="ss-home-body mt-8 text-sm">
				The desktop app is not available on {os}. Browse{" "}
				<a className="ss-home-link" href={GITHUB_RELEASES_URL}>
					all releases
				</a>{" "}
				instead.
			</p>
		);
	}

	if (isLoading) {
		return (
			<FlowButton
				className="mt-8 opacity-50 pointer-events-none"
				text={`Download for ${os}`}
				disabled
			/>
		);
	}

	return (
		<FlowButton
			className="mt-8"
			href={primary?.url ?? GITHUB_RELEASES_URL}
			text={`Download for ${os}`}
		/>
	);
}

type OSPanel = {
	title: string;
	match: (assetName: string) => boolean;
	/** Asset-label suffixes expected for this platform, used to size the
	 * disabled placeholder links while the real list is still loading. */
	suffixes: (keyof typeof ASSET_LABELS)[];
};

const OS_PANELS: OSPanel[] = [
	{ title: "Windows", match: (name) => name.endsWith(".exe"), suffixes: [".exe"] },
	{
		title: "macOS",
		match: (name) => name.endsWith(".dmg"),
		suffixes: ["-arm64.dmg", "-x64.dmg"],
	},
	{
		title: "Linux",
		match: (name) => name.endsWith(".AppImage") || name.endsWith(".deb"),
		suffixes: [".deb", ".AppImage"],
	},
];

export function AllReleasesLink() {
	return (
		<p className="ss-home-body text-sm">
			Looking for an older version, checksums or release notes?{" "}
			<a className="ss-home-link" href={GITHUB_RELEASES_URL}>
				Browse all releases on GitHub
			</a>
			.
		</p>
	);
}

export function OSDownloadGrid() {
	const { assets, isLoading } = useLatestRelease();

	return (
		<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
			{OS_PANELS.map((panel) => {
				// Sorted to the same fixed order as the loading placeholders below,
				// since GitHub doesn't guarantee asset order is stable across
				// releases — without this the real links can swap position right
				// as they replace the placeholders.
				const panelAssets = assets
					.filter((asset) => panel.match(asset.name))
					.toSorted(
						(a, b) =>
							panel.suffixes.findIndex((suffix) => a.name.endsWith(suffix)) -
							panel.suffixes.findIndex((suffix) => b.name.endsWith(suffix))
					);
				return (
					<div key={panel.title} className="ss-home-cell flex flex-col">
						<h3 className="ss-home-h3">{panel.title}</h3>
						<div className="mt-4 flex flex-col items-start gap-2">
							{isLoading
								? panel.suffixes.map((suffix) => (
										<span
											key={suffix}
											aria-disabled="true"
											className="ss-home-forward pointer-events-none opacity-50"
										>
											{ASSET_LABELS[suffix]}
											<DownloadIcon aria-hidden="true" className="size-3.5" />
										</span>
									))
								: panelAssets.map((asset) => (
										<a key={asset.name} className="ss-home-forward" href={asset.url}>
											{getAssetLabel(asset.name)}
											<DownloadIcon aria-hidden="true" className="size-3.5" />
										</a>
									))}
						</div>
					</div>
				);
			})}
		</div>
	);
}
