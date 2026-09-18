import type { Metadata } from "next";
import Link from "next/link";

/**
 * Terms of Service. Plain long-form prose, laid out like a blog post: the
 * `ss-home-pad` + `max-w-3xl` + Tailwind `prose` wrapper is copied from
 * `app/(home)/blog/[slug]/page.tsx`. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, which supplies the dark palette that
 * `prose-invert` assumes, plus the navigation and footer.
 *
 * Substantive changes from the version this replaces, all because the product
 * changed shape:
 *
 * - **The content licence grant is gone.** The old section 5 took a
 *   "worldwide, non-exclusive, royalty-free licence to use, reproduce, modify,
 *   adapt, publish, translate ... and display" anything you submitted. A local
 *   app receives nothing, so the grant covered nothing we hold, and asking for
 *   it contradicted the product.
 * - **Account sections are gone.** There is no account in the desktop app, so
 *   terms about safeguarding passwords and terminating accounts described
 *   something that no longer exists.
 * - **The date is a constant.** The old page rendered
 *   `new Date().toLocaleDateString()`, which caused a hydration mismatch and
 *   told every reader the terms had changed the moment they loaded the page.
 * - **Sections that were missing were added**: eligibility, acceptable use,
 *   termination, governing law, export controls, copyright complaints,
 *   assignment and force majeure.
 *
 * The licence description is deliberately precise: the repository is Apache-2.0
 * *except* `surfsense_backend/app/proprietary/`, which is BUSL-1.1 (see the
 * root LICENSE). Calling the whole thing Apache-2.0 would be wrong.
 *
 * Sections 12 and 13 stay in capitals. That is not shouting for its own sake: a
 * disclaimer of implied warranties has to be conspicuous to be effective, so
 * the text is kept short and left in caps rather than softened into paragraphs
 * that might not carry.
 */

const canonicalUrl = "https://www.surfsense.com/terms";

const metaTitle = "Terms of Service | SurfSense";
const metaDescription =
	"The terms for using the SurfSense desktop app, this website and paid plugin licences. The app is free, the source is public, and your documents stay yours.";

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
	},
};

/** Update on every material change, for the reasons in the header note. */
const LAST_UPDATED = "September 18, 2026";

/**
 * The governing law and the seat of arbitration.
 *
 * SET THIS. Until it names a real jurisdiction, section 14 falls back to "the
 * jurisdiction in which SurfSense is established", which is honest but weak:
 * a court has to work out where that is before it can apply anything, and a
 * vague choice-of-law clause is the first thing an opponent attacks. Naming
 * the country or state where the entity behind SurfSense is registered is a
 * one-line change here and makes the whole section enforceable.
 */
const GOVERNING_LAW: string | null = null;

const forum = GOVERNING_LAW ?? "the jurisdiction in which SurfSense is established";

/** Matches the `prose` treatment used for blog posts. */
const PROSE =
	"prose prose-invert max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-a:no-underline";

export default function TermsOfService() {
	return (
		<div className="ss-home-pad pt-16 pb-20">
			<div className="mx-auto max-w-3xl">
				<div className="mb-10 space-y-4">
					<h1 className="ss-home-h2">Terms of Service</h1>
					<p className="text-muted-foreground text-sm">Last updated: {LAST_UPDATED}</p>
				</div>

				<div className={PROSE}>
					<p>
						These terms are the agreement between you and SurfSense covering the SurfSense desktop
						application, this website, and any licence you buy from us. Downloading or using the
						application, or using this website, means you accept them. If you do not accept them, do
						not use either.
					</p>
					<p>
						They are shorter than terms of this kind usually are, because an application that runs
						on your own computer and holds no account needs fewer rules. Where an open source
						licence in our repository covers a file, that licence governs that file and these terms
						do not override it.
					</p>

					<h2>1. Who may use SurfSense</h2>
					<p>
						You must be old enough to enter a binding contract where you live, and at least 13, or
						16 in the European Economic Area and the United Kingdom. If you are using SurfSense for
						an employer, a firm or any other organisation, you confirm you are authorised to accept
						these terms for it, and "you" means that organisation as well.
					</p>
					<p>
						You may not use SurfSense if sanctions or export controls prohibit us from supplying
						you, as described in section 17.
					</p>

					<h2>2. The software and your rights in it</h2>
					<p>
						Most of SurfSense is open source under the Apache License 2.0, which lets you run,
						modify, redistribute and build on it commercially, subject to that licence's terms. One
						directory is not: <code>surfsense_backend/app/proprietary/</code> is licensed under the
						Business Source License 1.1. The{" "}
						<a href="https://github.com/MODSetter/SurfSense/blob/main/LICENSE">LICENSE file</a> in
						the repository is the authority on which terms apply to which files, and it wins over
						this page wherever the two disagree.
					</p>
					<p>
						Third-party components keep the licences their own authors gave them. That includes the
						language models, the speech model, the document parser and the other components bundled
						with the installer or downloaded by it. Some carry their own use restrictions, which
						travel with them and are not ours to waive, so check them if your use is commercial or
						unusual.
					</p>
					<p>
						The SurfSense name and logo are not covered by those licences. You may say your project
						is built on SurfSense. You may not publish a fork under our name, or brand anything in a
						way that suggests we released or endorsed it.
					</p>

					<h2>3. Your documents and everything you make</h2>
					<p>
						Your documents, your prompts, your chats and every deck, report, spreadsheet, podcast or
						summary the application produces from them are yours. We claim no licence, no ownership
						and no right to use any of it. We could not exercise such a right if we had one, because
						the application keeps your material on your machine and never transmits it to us.
					</p>
					<p>
						That cuts both ways. You are responsible for having the right to use whatever you put
						into it, and for what you do with what comes out. Do not use SurfSense to infringe
						copyright, to breach a confidentiality or professional duty you are under, or to process
						personal data you have no lawful basis to process. If you handle client or patient
						material, your own regulator's rules continue to apply and this software does not
						discharge them for you.
					</p>
					<p>
						Keep your own backups. The application writes to a folder on your disk, and a failed
						drive, a deleted folder or an operating system fault takes your workspace with it. We
						hold no copy and cannot restore anything.
					</p>

					<h2>4. Acceptable use</h2>
					<p>
						You agree not to use SurfSense or this website to break the law, infringe anyone's
						rights, or harm anyone. Specifically, do not use them to:
					</p>
					<ul>
						<li>
							attack, overload, probe or gain unauthorised access to any system, network or account,
							including ours;
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
							of its terms;
						</li>
						<li>
							remove, disable or work around a licence check, rate limit or other technical
							protection;
						</li>
						<li>
							resell, sublicense or redistribute a licence file or the plugin service as your own
							product.
						</li>
					</ul>
					<p>
						Because the application runs locally, we mostly cannot see what you do with it and do
						not police it. Section 4 still binds you, and it is enforceable for anything that
						touches a service we run.
					</p>

					<h2>5. Licences, trials, payment and refunds</h2>
					<p>
						The application and its updates are free. A licence adds the scraper plugins and
						priority support and gates nothing else. You can start with a 30-day licence on an email
						address without giving us a card. Paid licences are sold through Stripe, and team
						licences are arranged by email.
					</p>
					<p>
						A licence is verified on your own machine against a cryptographic signature, so it keeps
						working offline. Do not share, resell or publish your licence file, and do not attempt
						to defeat the check. A licence is for the person or organisation it was issued to.
					</p>
					<p>
						When a licence expires, the plugins and priority support stop. The application and every
						future version of it keep working, and nothing you created with it is locked, degraded
						or taken away.
					</p>
					<p>
						If a licence does not do what this site says it does, email us within 30 days of buying
						it and we will refund it in full. Beyond that, fees already paid are not refundable
						except where the law says otherwise, and your statutory cancellation rights as a
						consumer are unaffected. We may change prices for future purchases; a licence you have
						already bought keeps the terms and price you bought it on.
					</p>

					<h2>6. The scraper plugins and the service behind them</h2>
					<p>
						The plugins are the one paid feature that uses a service we operate. When you ask a
						plugin to fetch something, your request and its target reach that service so it can
						carry out the fetch.
					</p>
					<p>
						Use it lawfully, for data you are entitled to collect, at a reasonable volume, and
						respect the terms and technical signals of the sites you point it at. We may apply rate
						limits, and we may suspend or terminate a licence being used to attack a third party, to
						collect data unlawfully, or obtained by fraud or chargeback. Where the problem is
						fixable we will tell you before cutting you off, unless the abuse is serious enough that
						waiting would cause harm.
					</p>

					<h2>7. Models and services you choose</h2>
					<p>
						SurfSense can use a model you run locally or one reached with an API key you supply. If
						you supply a key, your agreement for that model is with its provider, on their terms and
						at their prices. You are responsible for staying within those terms, for what the key is
						permitted to do, and for the bill it generates.
					</p>
					<p>
						We do not control those providers and we do not promise they will be available,
						accurate, private or unchanged. If a provider alters its models, pricing or policies, or
						withdraws access entirely, that is a matter between you and them.
					</p>

					<h2>8. What the output is worth</h2>
					<p>
						Language models produce fluent text that is sometimes wrong, and they can invent
						citations, figures and quotations that look correct. Nothing SurfSense generates is
						legal, financial, medical, tax or other professional advice, and none of it is a
						substitute for review by someone qualified to give it.
					</p>
					<p>
						You are responsible for checking anything you rely on or send to someone else. The
						application cites the sources behind an answer specifically so that you can check it,
						and we expect you to.
					</p>

					<h2>9. Changes to the software</h2>
					<p>
						We are actively developing SurfSense. Features will be added, changed and sometimes
						removed, and a capability present in one version may not be present in the next. We try
						not to break things people depend on, and the changelog records what moved.
					</p>
					<p>
						Because the application runs on your machine, you decide when to update. An older
						version keeps working until you replace it, though we only support the current one and
						only the current one receives security fixes.
					</p>

					<h2>10. Ending this agreement</h2>
					<p>
						You can end it at any time by stopping use and, if you like, deleting the application
						and its data folder. Nothing further is required of you.
					</p>
					<p>
						We may suspend or terminate your access to services we run, including the plugin service
						and this website, if you materially breach these terms, and we may terminate a licence
						for the reasons in section 6. Termination of a service does not revoke your rights under
						the open source licences covering the code, which continue on their own terms. Sections
						3, 8, 12, 13, 14, 15 and 19 survive termination.
					</p>

					<h2>11. This website</h2>
					<p>
						The website is provided for information, documentation, downloads and the free chat
						pages. Do not attempt to disrupt it, circumvent its abuse protections, or use automated
						means to hammer it. The free chat pages are anonymous and rate limited; do not paste
						confidential material into them, and do not treat them as a private channel.
					</p>

					<h2>12. Disclaimer of warranties</h2>
					<p>
						We build this carefully and we want it to work well for you. What follows is the legal
						floor beneath that, in capitals because a disclaimer of implied warranties has to be
						conspicuous to be effective.
					</p>
					<p className="font-semibold uppercase">
						The software and this website are provided "as is" and "as available", without warranty
						of any kind. To the fullest extent permitted by law, we disclaim all warranties, express
						or implied, including any implied warranty of merchantability, fitness for a particular
						purpose, accuracy, quiet enjoyment and non-infringement. We do not warrant that the
						software will be uninterrupted, secure or error free, that defects will be corrected, or
						that it will meet your requirements or produce accurate output.
					</p>

					<h2>13. Limitation of liability</h2>
					<p className="font-semibold uppercase">
						To the fullest extent permitted by law, SurfSense and its contributors and suppliers
						will not be liable for lost profits, lost revenue, lost goodwill, lost or corrupted
						data, business interruption, or any indirect, special, incidental, consequential,
						exemplary or punitive damages, however caused and on any theory of liability, even if
						advised of the possibility.
					</p>
					<p className="font-semibold uppercase">
						Our total aggregate liability for all claims relating to the software, this website or
						these terms is limited to the greater of the total amount you paid us in the twelve
						months before the claim arose, or fifty US dollars.
					</p>
					<p>
						Some jurisdictions do not allow the exclusion of certain warranties or the limitation of
						certain damages, so parts of sections 12 and 13 may not apply to you. Where that is so,
						they apply only as far as that jurisdiction permits. Nothing in these terms limits
						liability for fraud or fraudulent misrepresentation, for death or personal injury caused
						by negligence, or for anything else that cannot lawfully be limited. If you are a
						consumer, your mandatory statutory rights are unaffected.
					</p>

					<h2>14. Indemnity</h2>
					<p>
						You agree to indemnify and hold harmless SurfSense and its contributors from claims,
						liabilities, damages and reasonable legal costs arising out of your use of the software
						or this website in breach of these terms or of the law. That expressly includes your use
						of the scraper plugins against a third party, and any claim that material you processed
						infringed someone's rights.
					</p>

					<h2>15. Governing law and disputes</h2>
					<p>
						These terms, and any dispute arising out of them or out of your use of SurfSense, are
						governed by the laws of {forum}, without regard to its conflict of laws rules.
					</p>
					<p>
						We would much rather fix a problem than argue about one, so please email us first and
						give us a genuine chance to resolve it. If that fails, you and we agree that the dispute
						will be settled by binding arbitration before a single arbitrator, conducted in English,
						seated in {forum}, and brought on an individual basis rather than as a class,
						consolidated or representative action. Where a claim proceeds in court instead, each of
						us waives any right to a jury trial.
					</p>
					<p>
						Two exceptions. Either of us may bring a qualifying claim in a small claims court, and
						either of us may ask a court for an injunction to stop misuse of intellectual property
						or confidential information without first arbitrating.
					</p>
					<p>
						If you are a consumer resident in the European Economic Area or the United Kingdom,
						nothing in this section removes your right to bring proceedings in the courts of the
						country where you live, or to rely on the mandatory consumer protections of that
						country's law.
					</p>

					<h2>16. Copyright complaints</h2>
					<p>
						If you believe material on this website infringes your copyright, email{" "}
						<a href="mailto:rohan@surfsense.com">rohan@surfsense.com</a> identifying the work, the
						material you say infringes it and where to find it, your contact details, and a
						statement that you hold the right or act for the person who does. We will review it and
						remove material where the complaint is well founded. We do not host the documents you
						process in the application, so a complaint about those has to go to whoever is hosting
						them.
					</p>

					<h2>17. Export controls and sanctions</h2>
					<p>
						The software may be subject to export control and sanctions laws. You confirm you are
						not located in, and will not use or re-export it to, a country or party subject to an
						embargo or restriction that would prohibit us from supplying you, and that you are not a
						person listed on an applicable restricted-party list. You are responsible for complying
						with those laws where you are.
					</p>

					<h2>18. Changes to these terms</h2>
					<p>
						We may update these terms as the product or the law changes. The date at the top of this
						page moves when we do, and for a material change affecting people holding a paid licence
						we will email the address on that licence. Continuing to use the software or this
						website after a change takes effect means you accept the updated terms. If you do not
						accept them, stop using them, and section 5 still governs any refund you are due.
					</p>

					<h2>19. The rest</h2>
					<p>
						If a provision here is held unenforceable, the rest stays in force and that provision is
						narrowed to the minimum needed to make it valid. If we do not enforce a right
						immediately, we have not waived it. You may not assign these terms without our consent;
						we may assign them to a successor in connection with a merger, acquisition or sale of
						assets, and we will say so on this page. Neither of us is liable for a failure to
						perform caused by something genuinely outside our control.
					</p>
					<p>
						These terms, together with the licences in our repository and any separate written
						agreement covering a team licence, are the whole agreement between us about the
						software, and they create no rights for anyone who is not a party to them. Notices to us
						go to the email address below; notices to you go to the address on your licence or are
						posted on this site.
					</p>

					<h2>20. Contact</h2>
					<p>
						Questions about these terms go to{" "}
						<a href="mailto:rohan@surfsense.com">rohan@surfsense.com</a>. How we handle data is
						described in our <Link href="/privacy">Privacy Policy</Link>.
					</p>
				</div>
			</div>
		</div>
	);
}
