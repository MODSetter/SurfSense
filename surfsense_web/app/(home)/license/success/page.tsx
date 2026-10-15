import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { LicenseDownload } from "./license-download";

/**
 * Rendered in the site design, same as `/license`; see that page's comment.
 * The install steps and the "lost the file" note are the same FAQ pattern
 * used there.
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
				shows each step. SurfSense never contacts a license server: the file is checked on your own
				machine, so it works offline and on every computer you install SurfSense on.
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
			<section className="py-20 md:py-28">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className={siteText.display}>Thanks, you are all set</h1>
					<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
						Your license file is below. Save it now: it is the thing that unlocks plugins and
						priority support, and we have also emailed you a copy.
					</p>
				</div>
			</section>

			<section className="border-t border-border py-16">
				<div className="max-w-xl">
					<Suspense fallback={null}>
						<LicenseDownload />
					</Suspense>
				</div>
			</section>

			<section className="border-t border-border" aria-labelledby="ss-license-success-faq-label">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<p className={siteText.eyebrow}>Next steps</p>
					<h2 id="ss-license-success-faq-label" className={cn(siteText.h2, "mt-2")}>
						Installing it
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
