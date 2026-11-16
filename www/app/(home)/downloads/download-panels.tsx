import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { DownloadIcon } from "@/components/ui/icons";
import {
	GITHUB_RELEASES_URL,
	getAssetLabel,
	platformOfAsset,
	type ReleaseAsset,
} from "@/features/downloads/app-release";

/** Through the counting redirect (`./[platform]/route.ts`) when it knows the file. */
function installerHref(asset: ReleaseAsset): string {
	const platform = platformOfAsset(asset.name);
	return platform ? `/downloads/${platform}?src=site` : asset.url;
}

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
		match: (name) => name.endsWith(".AppImage") || name.endsWith(".deb") || name.endsWith(".rpm"),
		suffixes: [".deb", ".rpm", ".AppImage"],
	},
];

export function AllReleasesLink() {
	return (
		<p className={cn(siteText.body, "rounded-3xl bg-muted px-6 py-8 text-center text-sm")}>
			Looking for an older version, checksums or release notes?{" "}
			<a className={siteText.link} href={GITHUB_RELEASES_URL}>
				Browse all releases on GitHub
			</a>
			.
		</p>
	);
}

/** One rounded card per system, each installer a pill with its download mark. */
export function OSDownloadGrid({ assets }: { assets: ReleaseAsset[] }) {
	return (
		<ul className="m-0 grid list-none gap-4 p-0 md:grid-cols-3">
			{OS_PANELS.map((panel) => {
				const panelAssets = assets
					.filter((asset) => panel.match(asset.name))
					.toSorted(
						(a, b) =>
							panel.suffixes.findIndex((suffix) => a.name.endsWith(suffix)) -
							panel.suffixes.findIndex((suffix) => b.name.endsWith(suffix))
					);
				return (
					<li
						key={panel.title}
						className="flex flex-col rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8"
					>
						<h3 className={siteText.h3}>{panel.title}</h3>
						<div className="mt-5 flex flex-col gap-2">
							{panelAssets.map((asset) => (
								<a
									key={asset.name}
									href={installerHref(asset)}
									className="flex h-11 items-center justify-between gap-3 rounded-full bg-secondary px-5 text-sm font-medium text-foreground transition-colors duration-150 ease-out hover:bg-accent active:bg-[color-mix(in_oklch,var(--accent),var(--foreground)_8%)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
								>
									{getAssetLabel(asset.name)}
									<DownloadIcon aria-hidden="true" className="size-4 shrink-0" />
								</a>
							))}
						</div>
					</li>
				);
			})}
		</ul>
	);
}
