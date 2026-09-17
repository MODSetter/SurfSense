import type { Metadata } from "next";
import { ArrowRightIcon } from "@/components/ui/icons";
import { ResendDisclosure, TrialForm } from "./license-forms";

/**
 * Rendered in the site design: the palette, ruled column, navigation and
 * footer all come from `app/(home)/layout.tsx`, and every style resolves from
 * `app/(home)/home.css`. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * The trial is folded straight into the hero as the page's one primary
 * action, the same compact shape `/sunset` uses for its export button:
 * headline, subtitle, form, done, no separate ruled band underneath it.
 * Resending an existing license is secondary and stays a one-line disclosure
 * under the trial form rather than a section of its own or a second page --
 * see `ResendDisclosure` in `license-forms.tsx` for why.
 *
 * The three explanatory blocks the old page ran as plain paragraphs are FAQ
 * content in substance: a reader arrives here with one of exactly three
 * questions, so they render as the same native `<details>` accordion the
 * homepage, pricing and plugins pages use, rather than a fourth design for
 * the same pattern.
 */

export const metadata: Metadata = {
	title: "Your license | SurfSense",
	description: "Get your SurfSense license file sent to your email again, or start a 30-day trial.",
	alternates: { canonical: "https://www.surfsense.com/license" },
};

const FAQ: { question: string; answer: React.ReactNode }[] = [
	{
		question: "Where does the file go?",
		answer: (
			<>
				Save the attached <code className="ss-home-mono">surfsense.lic</code>, open SurfSense, go to
				Settings, then License{" "}
				<ArrowRightIcon aria-hidden="true" className="inline size-3.5 align-[-0.1em]" /> and drop it
				in. Your license never expires the app: when it runs out, SurfSense keeps working and your
				data stays put.
			</>
		),
	},
	{
		question: "Bought for a team?",
		answer:
			"A team license is one file for everyone. It is sent only to the address that bought it, so ask whoever made the purchase to forward it to you.",
	},
	{
		question: "Cannot get into that inbox?",
		answer: (
			<>
				If you mistyped your email when buying, or no longer have access to it, we cannot send the
				file anywhere else automatically, since anyone could otherwise type your address and receive
				your license. Email{" "}
				<a className="ss-home-link" href="mailto:support@surfsense.com?subject=License%20recovery">
					support@surfsense.com
				</a>{" "}
				with your payment details (the charge on your card statement, or the last 4 digits, amount
				and date) and we will verify the purchase and fix it.
			</>
		),
	},
];

export default function LicensePage() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className="ss-home-display">Your SurfSense license</h1>
					<p className="ss-home-lede mx-auto mt-6 max-w-xl">
						Your license is a file, not an account.
					</p>
					<TrialForm />
					<ResendDisclosure />
				</div>
			</section>

			<section className="ss-home-rule" aria-labelledby="ss-license-faq-label">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">FAQ</p>
					<h2 id="ss-license-faq-label" className="ss-home-h2 mt-2">
						Common questions
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
