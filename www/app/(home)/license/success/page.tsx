import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { LicenseDownload } from "./license-download";

/**
 * Rendered in the site design, same as `/license`: the homepage's centred
 * heads, and the install steps and "lost the file" note as its FAQ pattern.
 */

export const metadata: Metadata = {
	title: "Thanks for buying SurfSense",
	robots: { index: false, follow: false },
};

const FAQ: { question: string; answer: React.ReactNode }[] = [
	{
		question: "How do I install it?",
		answer: (
			<>
				Save <code className="font-mono">surfsense.lic</code> somewhere you can find it, open
				SurfSense, go to Settings, then License{" "}
				<ArrowRightIcon aria-hidden="true" className="inline size-3.5 align-[-0.1em]" />, and drop
				the file in (or paste its contents). The{" "}
				<Link className={siteText.link} href="/license/activate">
					activation guide
				</Link>{" "}
				shows each step. The file is checked on your own machine, so it works offline and on every
				computer you install SurfSense on. Only the paid plugins send its key, to our plugin
				service, which checks it.
			</>
		),
	},
	{
		question: "Lose the file later?",
		answer: (
			<>
				Get it emailed again at{" "}
				<a className={siteText.link} href="/license">
					surfsense.com/license
				</a>
				, using the address you bought with.
			</>
		),
	},
];

export default function LicenseSuccessPage() {
	return (
		<>
			{/* The download sits in the hero, where /license and /downloads put their pill. */}
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Thank you</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>Thanks, you are all set</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					Your license file is below. Save it now: it is the thing that unlocks plugins and priority
					support, and we have also emailed you a copy.
				</p>
				<div className="mt-10">
					<Suspense fallback={null}>
						<LicenseDownload />
					</Suspense>
				</div>
			</section>

			<section className={sectionSpacing.foot} aria-labelledby="ss-license-success-faq-label">
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>Next steps</HomeBadge>
					<h2 id="ss-license-success-faq-label" className={cn(siteText.h2, "mt-4")}>
						Installing it
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
