import type { Metadata } from "next";
import Link from "next/link";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { ResendForm } from "./license-forms";

/**
 * Rendered in the site design: the palette, ruled column, navigation and
 * footer all come from `app/(home)/layout.tsx`; the page itself is Tailwind
 * plus the shared `siteText` styles. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * This page does one thing: send a licence file back to the address it was
 * issued to. Without accounts, that file is the only thing a customer holds,
 * so losing it has no other recovery path -- which is why `/license/success`
 * points here three times and `scripts/correct_license_email.py` hands the
 * customer back to it after a support fix.
 *
 * The trial form used to sit above this one. It now lives on `/downloads`,
 * where the 30-day licence is claimed alongside the installer it needs.
 *
 * The explanatory blocks the first version ran as plain paragraphs are FAQ
 * content in substance, so they render as the same native `<details>`
 * accordion the homepage, pricing and plugins pages use.
 */

export const metadata: Metadata = {
	title: "Get your SurfSense license file",
	description:
		"Have your SurfSense license file emailed to you again, using the address it was issued to.",
	// `seo/02-page-briefs.md` lists this route under "Pages that should be
	// noindex": it is a form keyed on an email address, and indexing it invites
	// abuse. No canonical alongside it -- the two directives contradict.
	robots: { index: false, follow: false },
};

const FAQ: { question: string; answer: React.ReactNode }[] = [
	{
		question: "Where does the file go?",
		answer: (
			<>
				Save the attached <code className="font-mono">surfsense.lic</code>, open SurfSense, go to
				Settings, then License{" "}
				<ArrowRightIcon aria-hidden="true" className="inline size-3.5 align-[-0.1em]" /> and drop it
				in. The{" "}
				<Link className={siteText.link} href="/license/activate">
					activation guide
				</Link>{" "}
				walks through it with screenshots. Your license never expires the app: when it runs out,
				SurfSense keeps working and your data stays put.
			</>
		),
	},
	{
		question: "Bought for your organisation?",
		answer:
			"An enterprise license is one file for everyone. It is sent only to the address that bought it, so ask whoever made the purchase to forward it to you.",
	},
	{
		question: "Cannot get into that inbox?",
		answer: (
			<>
				If you mistyped your email when buying, or no longer have access to it, we cannot send the
				file anywhere else automatically, since anyone could otherwise type your address and receive
				your license. Email{" "}
				<a className={siteText.link} href="mailto:rohan@surfsense.com?subject=License%20recovery">
					rohan@surfsense.com
				</a>{" "}
				with your payment details (the charge on your card statement, or the last 4 digits, amount
				and date) and we will verify the purchase and fix it.
			</>
		),
	},
	{
		question: "Do not have a license yet?",
		answer: (
			<>
				This page only sends back a license that already exists. The free 30-day license comes with
				the app, on{" "}
				<a className={siteText.link} href="/downloads">
					the download page
				</a>
				; to buy one, see{" "}
				<a className={siteText.link} href="/pricing">
					pricing
				</a>
				.
			</>
		),
	},
];

export default function LicensePage() {
	return (
		<>
			<section className="py-20 md:py-28">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className={siteText.display}>Get your license again</h1>
					<p className={cn(siteText.lede, "mx-auto mt-6 mb-10 max-w-xl")}>
						Your license is a file, not an account. Lost it? We will send it back.
					</p>
					<ResendForm />
					{/* The step after this one, for the reader whose file has just
					    landed: this page is where they arrive with no idea what a
					    .lic file is for. */}
					<p className="mt-10">
						<Link className={siteText.forward} href="/license/activate">
							Already have the file? Activate it{" "}
							<ArrowRightIcon aria-hidden="true" className="size-4" />
						</Link>
					</p>
				</div>
			</section>

			<section className="border-t border-border" aria-labelledby="ss-license-faq-label">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<p className={siteText.eyebrow}>FAQ</p>
					<h2 id="ss-license-faq-label" className={cn(siteText.h2, "mt-2")}>
						Common questions
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
