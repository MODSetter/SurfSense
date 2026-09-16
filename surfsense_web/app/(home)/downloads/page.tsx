import type { Metadata } from "next";
import { AllReleasesLink, OSDownloadGrid, PrimaryDownloadButton } from "./download-panels";

/**
 * Rendered in the site design: the palette, ruled column, navigation and
 * footer all come from `app/(home)/layout.tsx`, and every style resolves from
 * `app/(home)/home.css`. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * The hero's single button auto-detects the visitor's OS and links straight
 * to the matching installer (`PrimaryDownloadButton`, from
 * `lib/desktop-download-utils.ts` — the same hook the old homepage hero
 * used); the grid below it is the explicit fallback for anyone downloading
 * for a machine other than the one they're on.
 */

export const metadata: Metadata = {
	title: "Download SurfSense | Windows, macOS, Linux",
	description:
		"Download the SurfSense desktop app for Windows, macOS and Linux. Self-hosted, runs entirely on your machine.",
	alternates: { canonical: "https://www.surfsense.com/downloads" },
};

export default function DownloadsPage() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className="ss-home-display">Download SurfSense</h1>
					<p className="ss-home-lede mx-auto mt-6 max-w-xl">
						One installer, no account, no cloud. Pick your platform below.
					</p>
					<div className="mt-2 flex justify-center">
						<PrimaryDownloadButton />
					</div>
				</div>
			</section>

			<section className="ss-home-rule ss-home-rule-plain">
				<div className="ss-home-head ss-home-head-plain ss-home-head-tight">
					<p className="ss-home-eyebrow">Choose your platform</p>
					<h2 className="ss-home-h2 mt-2">Windows, macOS and Linux</h2>
				</div>

				<OSDownloadGrid />
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-pad py-10 text-center">
					<AllReleasesLink />
				</div>
			</section>
		</>
	);
}
