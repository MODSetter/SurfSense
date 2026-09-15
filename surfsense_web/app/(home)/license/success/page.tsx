import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";
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
				Save <code className="ss-home-mono">surfsense.lic</code> somewhere you can find it, open
				SurfSense, go to Settings, then License{" "}
				<ArrowRight aria-hidden="true" className="inline size-3.5 align-[-0.1em]" />, and drop the
				file in (or paste its contents). SurfSense never contacts a license server: the file is
				checked on your own machine, so it works offline and on every computer you install SurfSense
				on.
			</>
		),
	},
	{
		question: "Lose the file later?",
		answer: (
			<>
				Get it emailed again at{" "}
				<a className="ss-home-link" href="/license">
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
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className="ss-home-display">Thanks, you are all set</h1>
					<p className="ss-home-lede mx-auto mt-6 max-w-xl">
						Your license file is below. Save it now: it is the thing that unlocks plugins and
						priority support, and we have also emailed you a copy.
					</p>
				</div>
			</section>

			<section className="ss-home-rule ss-home-pad py-16">
				<div className="mx-auto max-w-xl">
					<Suspense fallback={null}>
						<LicenseDownload />
					</Suspense>
				</div>
			</section>

			<section className="ss-home-rule" aria-labelledby="ss-license-success-faq-label">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">Next steps</p>
					<h2 id="ss-license-success-faq-label" className="ss-home-h2 mt-2">
						Installing it
					</h2>
				</div>

				<div className="ss-home-grid border-t border-border">
					{FAQ.map((item) => (
						<details key={item.question} className="ss-home-faq">
							<summary className="ss-home-faq-summary">
								<span className="ss-home-h3">{item.question}</span>
								<span aria-hidden="true" className="ss-home-faq-marker" />
							</summary>
							<div className="ss-home-faq-answer">
								<p className="ss-home-body">{item.answer}</p>
							</div>
						</details>
					))}
				</div>
			</section>
		</>
	);
}
