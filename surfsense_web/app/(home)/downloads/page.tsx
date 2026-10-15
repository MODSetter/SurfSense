import type { Metadata } from "next";
import { TrialForm } from "@/app/(home)/license/license-forms";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { getReleaseAssets } from "@/lib/release-assets";
import { cn } from "@/lib/utils";
import { AllReleasesLink, OSDownloadGrid } from "./download-panels";

/**
 * Rendered in the site design: the palette, column, navigation and footer all
 * come from `app/(home)/layout.tsx`; the page uses the homepage's centred heads
 * and rounded cards. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 */

export const metadata: Metadata = {
	title: "Download SurfSense | Windows, macOS, Linux",
	description:
		"Download the SurfSense desktop app for Windows, macOS and Linux. Self-hosted, runs entirely on your machine.",
	alternates: { canonical: "https://www.surfsense.com/downloads" },
};

export default async function DownloadsPage() {
	const assets = await getReleaseAssets();

	return (
		<>
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Free desktop app</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>Download SurfSense</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					One installer, no account, no cloud.
				</p>
				<TrialForm label="Download" note="" />
			</section>

			{assets.length > 0 ? (
				<section className={sectionSpacing.foot} aria-labelledby="ss-downloads-platforms">
					<div className={cn("text-center", sectionSpacing.head)}>
						<HomeBadge>Choose your platform</HomeBadge>
						<h2 id="ss-downloads-platforms" className={cn(siteText.h2, "mt-4")}>
							Windows, macOS and Linux
						</h2>
					</div>

					<div className="mt-10 lg:mt-14">
						<OSDownloadGrid assets={assets} />
					</div>
				</section>
			) : null}

			<section className={cn(sectionSpacing.foot, assets.length > 0 ? undefined : "pt-16")}>
				<AllReleasesLink />
			</section>
		</>
	);
}
