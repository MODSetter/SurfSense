"use client";

import type { LucideIcon } from "lucide-react";
import { Apple, AppWindow, Download, TerminalSquare } from "lucide-react";
import { FlowButton } from "@/components/ui/flow-button";
import {
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
	const { os, primary, isMobileOS } = usePrimaryDownload();

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

	return (
		<FlowButton
			className="mt-8"
			href={primary?.url ?? GITHUB_RELEASES_URL}
			text={primary ? `Download for ${os}` : `Fetching the latest release for ${os}…`}
		/>
	);
}

type OSPanel = {
	title: string;
	icon: LucideIcon;
	match: (assetName: string) => boolean;
};

const OS_PANELS: OSPanel[] = [
	{ title: "Windows", icon: AppWindow, match: (name) => name.endsWith(".exe") },
	{ title: "macOS", icon: Apple, match: (name) => name.endsWith(".dmg") },
	{
		title: "Linux",
		icon: TerminalSquare,
		match: (name) => name.endsWith(".AppImage") || name.endsWith(".deb"),
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
	const assets = useLatestRelease();

	return (
		<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
			{OS_PANELS.map((panel) => {
				const panelAssets = assets.filter((asset) => panel.match(asset.name));
				return (
					<div key={panel.title} className="ss-home-cell flex flex-col">
						<panel.icon aria-hidden="true" className="size-6 text-muted-foreground" />
						<h3 className="ss-home-h3 mt-4">{panel.title}</h3>
						<div className="mt-4 flex flex-col items-start gap-2">
							{panelAssets.length > 0 ? (
								panelAssets.map((asset) => (
									<a key={asset.name} className="ss-home-forward" href={asset.url}>
										{getAssetLabel(asset.name)}
										<Download aria-hidden="true" className="size-3.5" />
									</a>
								))
							) : (
								<p className="ss-home-body text-sm">Fetching the latest release…</p>
							)}
						</div>
					</div>
				);
			})}
		</div>
	);
}
