import Link from "next/link";
import type { ReactNode } from "react";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { EMAIL } from "@/components/site/site-content";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { HomeDownloadButton } from "@/features/downloads/home-download-button";

/**
 * `/license`, `/license/activate` and `/license/success`: SurfSense needs no licence.
 *
 * The three routes stay because sent licence emails, Stripe's checkout and the app's own
 * error texts ("request a fresh copy at surfsense.com/license") link to them. Each now says
 * the same thing: from 2.4.0 every feature works with no licence file, and the licence
 * service closed with SurfSense Inc. on 27 November 2026. No form, no backend call.
 */

const FAQ: { question: string; answer: ReactNode }[] = [
	{
		question: "Do I still need my licence file?",
		answer: (
			<>
				No. From version 2.4.0, SurfSense unlocks every feature, the security questionnaire and
				contract redline jobs included, with no licence file. Update in the app from Settings ›
				About with Check now, or download the newest version from{" "}
				<Link className={siteText.link} href="/downloads">
					the download page
				</Link>
				.
			</>
		),
	},
	{
		question: "My app says the licence is missing, invalid or expired",
		answer:
			"Versions before 2.4.0 still check for a licence. Update to 2.4.0 or later and the message goes away; there is nothing to import. Your sources, chats and settings stay where they are.",
	},
	{
		question: "Can I have my licence file sent again?",
		answer:
			"No. The licence service closed with SurfSense Inc. on 27 November 2026, so licence files can no longer be issued, resent or renewed. None is needed from 2.4.0 on.",
	},
	{
		question: "I paid for a licence. Will I be charged again?",
		answer: (
			<>
				No. Every renewal has been cancelled. For a question about a past payment, email{" "}
				<a className={siteText.link} href={`mailto:${EMAIL}?subject=SurfSense%20licence`}>
					{EMAIL}
				</a>
				.
			</>
		),
	},
	{
		question: "On a Mac with SurfSense 2.3.0 or earlier?",
		answer:
			"Download 2.4.0 from the download page once and install it over the old app. Those versions can't install updates larger than 1 GiB by themselves.",
	},
];

export function NoLicenseNeeded({ heading }: { heading: string }) {
	return (
		<>
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>No licence needed</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>{heading}</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					SurfSense is free. From version 2.4.0 every feature, jobs included, works with no licence,
					account or trial.
				</p>
				<div className="mt-10 flex justify-center">
					<HomeDownloadButton tone="dark" placement="license" />
				</div>
				<p className={cn(siteText.body, "mt-5 text-sm")}>
					Why?{" "}
					<Link className={siteText.link} href="/pricing">
						SurfSense is now free
					</Link>
				</p>
			</section>

			<section className={sectionSpacing.foot} aria-labelledby="ss-license-faq-label">
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>FAQ</HomeBadge>
					<h2 id="ss-license-faq-label" className={cn(siteText.h2, "mt-4")}>
						Common questions
					</h2>
				</div>

				<div className="ss-home-grid mt-10 border-t border-border lg:mt-14">
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
