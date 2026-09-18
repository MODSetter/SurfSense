import { DownloadIcon } from "@/components/ui/icons";
import { GITHUB_RELEASES_URL, getAssetLabel, type ReleaseAsset } from "@/lib/app-release";

/**
 * Server components: the assets are resolved in `page.tsx` and handed down,
 * so the installer links are in the HTML rather than appearing after
 * hydration. This page is an SEO target, and a crawler used to see an empty
 * grid.
 */

type OSPanel = {
	title: string;
	match: (assetName: string) => boolean;
	/** Sort order within a panel: GitHub does not promise a stable asset
	 * order across releases. */
	suffixes: string[];
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

export function OSDownloadGrid({ assets }: { assets: ReleaseAsset[] }) {
	return (
		<div className="ss-home-grid ss-home-grid-3 ss-home-grid-dashed">
			{OS_PANELS.map((panel) => {
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
							{panelAssets.map((asset) => (
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
