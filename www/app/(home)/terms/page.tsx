import type { Metadata } from "next";
import Link from "next/link";
import { LegalDraftNotice } from "@/components/site/legal-draft-notice";
import { EMAIL, REPO_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";

/**
 * Terms of Service. Plain long-form prose, laid out like a blog post: the padded
 * `max-w-3xl` + Tailwind `prose` wrapper is copied from `app/(home)/blog/[slug]/page.tsx`.
 * `app/(home)/layout.tsx` supplies the light palette, the navigation and the footer.
 *
 * MAINTAINER REVIEW NEEDED BEFORE THIS SHIPS. Redrafted on 21 Nov 2026 for the free app:
 * SurfSense Inc. winds down on 27 Nov 2026, and SurfSense continues as a free project run
 * by its maintainer as an individual. What changed from the 22 Oct 2026 version:
 *
 * - **The party** is Rohan Verma, an individual, not "SurfSense" the company.
 * - **Licences, trials, payment and refunds are gone** (the old section 5), with the
 *   feature build request. Nothing is sold.
 * - **The hosted services are gone**: the scraper plugins and their service (old
 *   section 6), the licence server and the free chat pages. What is still served is static:
 *   this website, the plugin list and its OAuth files at plugins.surfsense.com, and the
 *   update and usage routes older apps call.
 * - **All code is Apache-2.0**: the BSL directories were relicensed, agreed in writing
 *   with SurfSense Inc.
 * - **Arbitration is gone**, which suits one person maintaining free software better than a
 *   company selling licences. Disputes go to the courts of `GOVERNING_LAW`.
 * - Sections 11 and 12 stay in capitals: a disclaimer of implied warranties has to be
 *   conspicuous to be effective.
 *
 * Before shipping: set `GOVERNING_LAW`, have the page read, then set `REVIEWED` to true.
 */

const canonicalUrl = "https://www.surfsense.com/terms";

const metaTitle = "Terms of Service | SurfSense";
const metaDescription =
	"The terms for using the free SurfSense desktop app and this website. The app is free and open source under Apache-2.0, and your documents stay yours.";

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
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense terms of service" }],
	},
};

/** Set to true once the maintainer has reviewed this redraft; until then the page says so. */
const REVIEWED = false;

/** Update on every material change. A constant, so the date never moves on its own. */
const LAST_UPDATED = "November 27, 2026";

/**
 * The governing law and the courts, for section 14. SET THIS to the country, and state if
 * any, where the maintainer lives. Until then the section names that place in words, which
 * is honest but weak: a court has to work out where it is before it can apply anything.
 */
const GOVERNING_LAW: string | null = null;

const forum = GOVERNING_LAW ?? "the place where the maintainer is resident";

/** Matches the `prose` treatment used for blog posts. */
const PROSE =
	"prose max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-a:no-underline";

export default function TermsOfService() {
	return (
		<div className="pt-16 pb-20">
			<div className="mx-auto max-w-3xl">
				<div className="mb-10 space-y-4 text-center">
					<h1 className={siteText.h2}>Terms of Service</h1>
					<p className="text-muted-foreground text-sm">Last updated: {LAST_UPDATED}</p>
				</div>

				<LegalDraftNotice reviewed={REVIEWED} />

				<div className={PROSE}>
					<p>
						These terms cover the SurfSense desktop application and this website. SurfSense is a
						free, open-source project maintained by Rohan Verma, an individual ("I", "me"). Until 27
						November 2026 it was published by SurfSense Inc., which has wound down; from that date
						these terms are between you and me. Downloading or using the application, or using this
						website, means you accept them. If you do not accept them, do not use either.
					</p>
					<p>
						They are short because SurfSense is free, runs on your own computer, and has no account,
						no licence and no hosted service. Where an open source licence in the repository covers
						a file, that licence governs the file and these terms do not override it.
					</p>

					<h2>1. Who may use SurfSense</h2>
					<p>
						You must be old enough to enter a binding agreement where you live, and at least 13, or
						16 in the European Economic Area and the United Kingdom. If you use SurfSense for an
						employer or another organisation, you confirm you may accept these terms for it.
					</p>

					<h2>2. The software and your rights in it</h2>
					<p>
						SurfSense is open source under the Apache License 2.0, which lets you run, modify,
						redistribute and build on it, commercially too, under that licence's terms. From version
						2.4.0 that includes the code and the job packs that were previously under the Business
						Source License 1.1 or not published. The{" "}
						<a href={`${REPO_URL}/blob/main/LICENSE`}>LICENSE files in the repository</a> are the
						authority on which terms apply to which files, and they win over this page wherever the
						two disagree.
					</p>
					<p>
						SurfSense is free. Nothing in it is sold, no feature needs a licence, and there is no
						paid plan, trial or subscription. Licence files issued before the wind-down are no
						longer needed and are not renewed.
					</p>
					<p>
						Third-party components keep the licences their own authors gave them. That includes the
						language models, the speech model, the document parser and the other components bundled
						with the installer or downloaded by it. Some carry their own use restrictions, which
						travel with them, so check them if your use is commercial or unusual.
					</p>
					<p>
						The SurfSense name and logo are not covered by those licences. You may say your project
						is built on SurfSense. You may not publish a fork under the SurfSense name, or brand
						anything in a way that suggests I released or endorsed it.
					</p>

					<h2>3. Your documents and everything you make</h2>
					<p>
						Your documents, your prompts, your chats and everything the application produces from
						them are yours. I claim no licence, ownership or right to use any of it, and the
						application keeps it on your computer without sending it to me.
					</p>
					<p>
						You are responsible for having the right to use whatever you put into SurfSense, and for
						what you do with what comes out. Do not use it to infringe copyright, to breach a
						confidentiality or professional duty you are under, or to process personal data you have
						no lawful basis to process. If you handle client or patient material, your own
						regulator's rules still apply and this software does not discharge them for you.
					</p>
					<p>
						Keep your own backups. The application writes to a folder on your disk, and a failed
						drive, a deleted folder or an operating system fault takes your workspace with it. I
						hold no copy and cannot restore anything.
					</p>

					<h2>4. Acceptable use</h2>
					<p>
						Do not use SurfSense or this website to break the law, infringe anyone's rights or harm
						anyone. In particular, do not use them to:
					</p>
					<ul>
						<li>
							attack, overload, probe or gain unauthorised access to any system, network or account,
							including this website;
						</li>
						<li>
							generate or distribute malware, spam, phishing material, or content that sexually
							exploits children;
						</li>
						<li>
							harass or threaten people, or produce material designed to defraud or impersonate
							someone;
						</li>
						<li>
							collect personal data at scale without a lawful basis, or scrape a service in breach
							of its terms.
						</li>
					</ul>
					<p>
						The application runs on your computer, so I cannot see what you do with it and do not
						police it. These rules still bind you.
					</p>

					<h2>5. Models, plugins and services you choose</h2>
					<p>
						SurfSense can use a model you run on your computer, or one reached with an API key you
						supply. With a key, your agreement for that model is with its provider, on their terms
						and at their prices. You are responsible for staying within those terms and for the
						bill.
					</p>
					<p>
						The same goes for a third-party plugin, an MCP server or a web search server you
						connect: each is run by someone else, under their terms. I do not control those
						providers and do not promise they will be available, accurate, private or unchanged.
					</p>

					<h2>6. What the output is worth</h2>
					<p>
						Language models produce fluent text that is sometimes wrong, and they can invent
						citations, figures and quotations that look correct. Nothing SurfSense generates is
						legal, financial, medical, tax or other professional advice, and none of it replaces
						review by someone qualified to give it. That includes what its jobs write, such as a
						filled-in security questionnaire or a redlined contract.
					</p>
					<p>
						You are responsible for checking anything you rely on or send to someone else. The
						application cites the sources behind an answer so that you can check it.
					</p>

					<h2>7. Changes to the software</h2>
					<p>
						SurfSense is maintained as a side project, so updates come at the pace one person can
						manage. Features may be added, changed or removed, and nothing here promises any further
						release, fix or support.
					</p>
					<p>
						Because the application runs on your computer, you decide when to update. An older
						version keeps working until you replace it, though only the newest receives fixes.
					</p>

					<h2>8. What the website serves</h2>
					<p>
						This website offers information, documentation and downloads. It also serves a few
						static files and routes that the application reads: the list of third-party plugins and
						the files OAuth plugin sign-in uses, at plugins.surfsense.com, and the update and usage
						routes older versions call. The hosted services that ran before the wind-down, including
						licences and trials, SurfSense's own scraper plugins, the hosted web search and the free
						chat pages, have closed. Do not attempt to disrupt the website or use automated means to
						hammer it.
					</p>

					<h2>9. Support</h2>
					<p>
						There is no paid support. Bugs and feature requests go to{" "}
						<a href={`${REPO_URL}/issues`}>GitHub issues</a>, and I answer them, and email, as time
						allows.
					</p>

					<h2>10. Ending this agreement</h2>
					<p>
						You can end it at any time by stopping use and, if you like, deleting the application
						and its data folder. I may stop offering this website or any file it serves at any time.
						Ending this agreement does not take away your rights under the open source licences
						covering the code, which continue on their own terms. Sections 3, 6, 11, 12, 13, 14 and
						17 survive it.
					</p>

					<h2>11. Disclaimer of warranties</h2>
					<p>
						SurfSense is built with care and given away for free. What follows is the legal floor
						beneath that, in capitals because a disclaimer of implied warranties has to be
						conspicuous to be effective.
					</p>
					<p className="font-semibold uppercase">
						The software and this website are provided "as is" and "as available", without warranty
						of any kind. To the fullest extent permitted by law, I disclaim all warranties, express
						or implied, including any implied warranty of merchantability, fitness for a particular
						purpose, accuracy, quiet enjoyment and non-infringement. I do not warrant that the
						software will be uninterrupted, secure or error free, that defects will be corrected, or
						that it will meet your requirements or produce accurate output.
					</p>

					<h2>12. Limitation of liability</h2>
					<p className="font-semibold uppercase">
						To the fullest extent permitted by law, neither I nor the contributors to SurfSense will
						be liable for lost profits, lost revenue, lost goodwill, lost or corrupted data,
						business interruption, or any indirect, special, incidental, consequential, exemplary or
						punitive damages, however caused and on any theory of liability, even if advised of the
						possibility.
					</p>
					<p className="font-semibold uppercase">
						Because SurfSense is free, my total aggregate liability for all claims relating to the
						software, this website or these terms is limited to fifty US dollars.
					</p>
					<p>
						Some jurisdictions do not allow the exclusion of certain warranties or the limitation of
						certain damages, so parts of sections 11 and 12 may not apply to you. Where that is so,
						they apply only as far as that jurisdiction permits. Nothing in these terms limits
						liability for fraud, for death or personal injury caused by negligence, or for anything
						else that cannot lawfully be limited. If you are a consumer, your mandatory statutory
						rights are unaffected.
					</p>

					<h2>13. Indemnity</h2>
					<p>
						You agree to indemnify me and the contributors to SurfSense against claims, liabilities,
						damages and reasonable legal costs arising out of your use of the software or this
						website in breach of these terms or of the law, including any claim that material you
						processed with it infringed someone's rights.
					</p>

					<h2>14. Governing law and disputes</h2>
					<p>
						These terms, and any dispute arising out of them or out of your use of SurfSense, are
						governed by the laws of {forum}, without regard to its conflict of laws rules, and the
						courts there have jurisdiction. Please email me first: I would much rather fix a problem
						than argue about one.
					</p>
					<p>
						If you are a consumer resident in the European Economic Area or the United Kingdom,
						nothing in this section removes your right to bring proceedings in the courts of the
						country where you live, or to rely on the mandatory consumer protections of its law.
					</p>

					<h2>15. Copyright complaints</h2>
					<p>
						If you believe material on this website infringes your copyright, email{" "}
						<a href={`mailto:${EMAIL}`}>{EMAIL}</a> identifying the work, the material you say
						infringes it and where to find it, your contact details, and a statement that you hold
						the right or act for the person who does. I will review it and remove material where the
						complaint is well founded. This website does not host the documents you process in the
						application.
					</p>

					<h2>16. Changes to these terms</h2>
					<p>
						I may update these terms as the project or the law changes, and the date at the top of
						this page moves when I do. Continuing to use the software or this website after a change
						takes effect means you accept the updated terms.
					</p>

					<h2>17. The rest</h2>
					<p>
						If a provision here is held unenforceable, the rest stays in force and that provision is
						narrowed to the minimum needed to make it valid. If I do not enforce a right
						immediately, I have not waived it. I may hand the project and these terms to another
						maintainer, and will say so on this page. Neither of us is liable for a failure caused
						by something genuinely outside our control. These terms, together with the licences in
						the repository, are the whole agreement between us about the software, and they create
						no rights for anyone who is not a party to them.
					</p>

					<h2>18. Contact</h2>
					<p>
						Questions about these terms go to <a href={`mailto:${EMAIL}`}>{EMAIL}</a>. How data is
						handled is described in the <Link href="/privacy">Privacy Policy</Link>.
					</p>
				</div>
			</div>
		</div>
	);
}
