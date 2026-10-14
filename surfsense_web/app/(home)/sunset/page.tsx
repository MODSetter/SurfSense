import type { Metadata } from "next";
import Link from "next/link";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { type GuideStep, GuideSteps } from "@/components/site/guide-steps";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";
import { SunsetExport } from "./sunset-export";

/**
 * Rendered in the site design: the palette, column, navigation and footer all
 * come from `app/(home)/layout.tsx`; the page uses the homepage's centred
 * heads and the shared rounded step cards. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 */

export const metadata: Metadata = {
	title: "SurfSense is moving | SurfSense",
	robots: { index: false, follow: false },
};

/**
 * The day the purge runs, written out: the page must still read correctly
 * after it, which a countdown would not. `docs/architecture/sunset.md` is the
 * source.
 */
const DELETION_DATE = "18 October 2026";

/**
 * The move, in the order someone does it.
 *
 * Labels are quoted from the desktop app rather than paraphrased, so the page
 * and the app do not name the same control two ways: "Import from SurfSense
 * cloud" and "Upload" are the literal strings in
 * `surfsense_local/frontend/src/features/settings/settings-dialog.tsx` and
 * `features/migration/import-bundle.tsx`, and what does and does not come
 * across is the same claim as that row's own tooltip.
 *
 * The three in-app screenshots are captured from the running app rather than
 * drawn; `scripts/capture-guide-shots.mjs` regenerates them.
 */
const STEPS: GuideStep[] = [
	{
		title: "Export your cloud data",
		body: `Your cloud data is deleted on ${DELETION_DATE}, and an export made before then is the only copy you keep. Save the ZIP somewhere you will find it again. You need it in step five.`,
		control: <SunsetExport />,
	},
	{
		title: "Download the desktop app",
		body: "An installer for Windows, macOS or Linux. There is no account to create, and it runs on your own machine.",
		action: { href: "/downloads", label: "Go to downloads" },
	},
	{
		title: "Open Settings in the app",
		body: "Install and open it, then click the gear at the bottom of the left rail.",
		shot: {
			src: "/sunset/03-settings.png",
			alt: "The bottom-left corner of the SurfSense window, where a gear icon sits below the sidebar.",
			width: 704,
			height: 468,
		},
	},
	{
		title: "Find the import row in General",
		body: 'Settings opens on General. The row you want is "Import from SurfSense cloud", under Appearance.',
		shot: {
			src: "/sunset/04-general.png",
			alt: 'SurfSense Settings open on General, showing an "Import from SurfSense cloud" row with an Upload button.',
			width: 2000,
			height: 1280,
		},
	},
	{
		title: "Upload the ZIP",
		body: "Click Upload and pick the ZIP. Your workspaces, folders and chat threads come across, and the app indexes the documents on your machine afterwards.",
		shot: {
			src: "/sunset/05-upload.png",
			alt: 'The "Import from SurfSense cloud" row and its Upload button, close up.',
			width: 1600,
			height: 168,
		},
	},
];

export default function SunsetPage() {
	return (
		<>
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Cloud data deleted on {DELETION_DATE}</HomeBadge>
				<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
					SurfSense is moving to a local app
				</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					The cloud service is export-only, and everything stored in it is deleted on{" "}
					<strong className="whitespace-nowrap text-foreground">{DELETION_DATE}</strong>. Export
					before then.
				</p>
			</section>

			<section className={sectionSpacing.foot} aria-labelledby="ss-sunset-steps">
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>Moving your data</HomeBadge>
					<h2 id="ss-sunset-steps" className={cn(siteText.h2, "mt-4")}>
						Five steps to the desktop app
					</h2>
				</div>

				<div className="mt-10 lg:mt-14">
					<GuideSteps steps={STEPS} />
				</div>
			</section>

			<section className={sectionSpacing.foot}>
				<p className={cn(siteText.body, "rounded-3xl bg-muted px-6 py-8 text-center text-sm")}>
					A fresh install shows the same Upload button on its empty workspace screen, so you can
					import before you do anything else. If something did not come across,{" "}
					<Link className={siteText.link} href="/contact">
						tell us
					</Link>
					.
				</p>
			</section>
		</>
	);
}
