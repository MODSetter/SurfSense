import type { Metadata } from "next";
import Link from "next/link";
import { type GuideStep, GuideSteps } from "@/components/site/guide-steps";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

/**
 * Rendered in the site design: the palette, ruled column, navigation and
 * footer all come from `app/(home)/layout.tsx`; the page itself is Tailwind
 * plus the shared `siteText` styles. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * The one place the activation steps live. All three license emails link here
 * (`app/license/email/message.py`), as do `/license` and `/license/success`,
 * which used to carry their own prose copy of the same instruction.
 *
 * Indexed, unlike its siblings: `/license` and `/license/success` are noindex
 * because one is a form keyed on an email address and the other serves a
 * license file. This page is a help document with neither.
 */

const canonicalUrl = "https://www.surfsense.com/license/activate";

const metaTitle = "Activate your SurfSense license";
const metaDescription =
	"How to add your SurfSense license file to the desktop app, step by step: save the .lic file, open Settings, then License, and check that it reads Active.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/**
 * Activation, in the order someone does it.
 *
 * Install comes first because a trial license is handed to an address rather
 * than to an installation, so the recipient may not have the app yet. That is
 * the same order the license email uses.
 *
 * Labels are quoted from the desktop app rather than paraphrased: "Add
 * license", "Choose license file" and the paste box are the literal controls
 * in `surfsense_local/frontend/src/features/license/license-settings.tsx`.
 * `scripts/capture-guide-shots.mjs` regenerates the screenshots.
 */
const STEPS: GuideStep[] = [
	{
		title: "Install SurfSense",
		body: "Skip this if you already have the app. One installer for Windows, macOS or Linux.",
		action: { href: "/downloads", label: "Go to downloads" },
	},
	{
		title: "Save the license file",
		body: (
			<>
				It arrived as an email attachment named <code className="font-mono">surfsense.lic</code>.
				Save it somewhere you can find it again.
			</>
		),
	},
	{
		title: "Open Settings, then License",
		body: "Click the gear at the bottom of the left rail, then choose License in the sidebar.",
		shot: {
			src: "/license/03-license-section.png",
			alt: 'SurfSense Settings open on License, reading "No license on this device" beside an Add license button.',
			width: 2000,
			height: 1280,
		},
	},
	{
		title: "Add the file",
		body: 'Click "Add license", then either choose the .lic file or paste its contents into the box.',
		shot: {
			src: "/license/04-add-dialog.png",
			alt: "The Add license dialog, offering a Choose license file button and a box to paste the file into.",
			width: 880,
			height: 648,
		},
	},
	{
		title: "Check that it reads Active",
		body: "Your plan, the address the license is tied to, and the expiry date appear together with an Active badge. Nothing was sent anywhere to get there.",
		shot: {
			src: "/license/05-active.png",
			alt: "The License section showing an Individual plan with an Active badge, the licensee email and an expiry date.",
			width: 2000,
			height: 1280,
		},
	},
];

const FAQ: { question: string; answer: React.ReactNode }[] = [
	{
		question: "Lost the file?",
		answer: (
			<>
				We will email it again to the address it was issued to, at{" "}
				<Link className={siteText.link} href="/license">
					surfsense.com/license
				</Link>
				. Nothing about your license changes when you ask for another copy.
			</>
		),
	},
	{
		question: 'It says "Clock is off"',
		answer:
			"SurfSense will not trust a license on a computer whose clock is more than five minutes behind the last time the app ran, or behind the date the license was issued. Put the clock right and it reads Active again.",
	},
	{
		question: "What happens when it expires?",
		answer:
			"The app keeps working and your documents stay where they are. Plugins and priority support stop, and every future version of the app is still free.",
	},
	{
		question: "Bought it for a team?",
		answer: (
			<>
				One file covers everyone on the plan, and it is emailed only to the address that paid, so
				ask whoever bought it to forward it to you. If that inbox is gone, email{" "}
				<a className={siteText.link} href="mailto:rohan@surfsense.com?subject=License%20recovery">
					rohan@surfsense.com
				</a>{" "}
				with your payment details.
			</>
		),
	},
];

export default function LicenseActivatePage() {
	return (
		<>
			<section className="py-20 md:py-28">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className={siteText.display}>Activate your license</h1>
					<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
						Your license is a file, not an account. SurfSense checks it on your own machine, so it
						works offline and on every computer you install the app on.
					</p>
				</div>
			</section>

			<section className="border-t border-border" aria-labelledby="ss-activate-steps">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<p className={siteText.eyebrow}>Activation</p>
					<h2 id="ss-activate-steps" className={cn(siteText.h2, "mt-2")}>
						Five steps to an active license
					</h2>
				</div>

				<GuideSteps steps={STEPS} />
			</section>

			<section className="border-t border-border" aria-labelledby="ss-activate-faq">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<p className={siteText.eyebrow}>FAQ</p>
					<h2 id="ss-activate-faq" className={cn(siteText.h2, "mt-2")}>
						If something is wrong
					</h2>
				</div>

				<div className="ss-home-grid">
					{FAQ.map((item) => (
						<SiteFaqItem key={item.question} question={item.question}>
							<p className={siteText.body}>{item.answer}</p>
						</SiteFaqItem>
					))}
				</div>
			</section>
		</>
	);
}
