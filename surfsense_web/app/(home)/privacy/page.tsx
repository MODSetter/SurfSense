import type { Metadata } from "next";
import Link from "next/link";

/**
 * Privacy Policy. Plain long-form prose, laid out like a blog post: the
 * `ss-home-pad` + `max-w-3xl` + Tailwind `prose` wrapper is copied from
 * `app/(home)/blog/[slug]/page.tsx` so a legal page reads like body text
 * rather than like a landing page. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, which is what supplies the dark palette
 * that `prose-invert` assumes, plus the navigation and footer.
 *
 * Every factual claim here was checked against the code, not against the
 * previous policy or the marketing copy. The version this replaced described
 * the hosted product and promised two safeguards that do not exist anywhere in
 * this repository: a "Google-certified Consent Management Platform" gating
 * advertising cookies, and honouring Global Privacy Control. Google AdSense was
 * removed from the site rather than documented, so the cookie story is now
 * analytics and function only. PostHog stays and is disclosed as what it is:
 * on by default, with no consent gate. If a consent gate ever ships, this page
 * and `instrumentation-client.ts` change in the same commit.
 *
 * Three claims are deliberately hedged because the obvious phrasing would be
 * false:
 *
 * - **The local database is not encrypted at rest.** Only provider API keys
 *   are (Fernet, key held by Electron `safeStorage`). "Your data is encrypted"
 *   would be untrue, so section 3.4 says to use full-disk encryption instead.
 * - **The Linux keychain fallback is weaker.** `safeStorage` falls back to
 *   Chromium plain-text encryption with no available keyring, per
 *   `electron/src/main/index.ts`.
 * - **Remote models receive document content.** Section 3.2 says so plainly
 *   rather than burying it, because it is the one case where "nothing leaves
 *   your machine" stops being true.
 *
 * Scope: the desktop app in `surfsense_local/` and this website. The hosted web
 * app and the older `surfsense_desktop/` wrapper that rendered it are being
 * retired and are not described here as current products.
 */

const canonicalUrl = "https://www.surfsense.com/privacy";

const metaTitle = "Privacy Policy | SurfSense";
const metaDescription =
	"What SurfSense collects and what it does not. The desktop app has no account and no telemetry, and your documents never leave your machine.";

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

/**
 * Update whenever a material change lands. A static constant rather than
 * `new Date()`: a render-time date causes a hydration mismatch and tells every
 * reader the document changed the moment they opened it.
 */
const LAST_UPDATED = "September 18, 2026";

/** Matches the `prose` treatment used for blog posts. */
const PROSE =
	"prose prose-invert max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-a:no-underline";

export default function PrivacyPolicy() {
	return (
		<div className="ss-home-pad pt-16 pb-20">
			<div className="mx-auto max-w-3xl">
				<div className="mb-10 space-y-4">
					<h1 className="ss-home-h2">Privacy Policy</h1>
					<p className="text-muted-foreground text-sm">Last updated: {LAST_UPDATED}</p>
				</div>

				<div className={PROSE}>
					<p>
						SurfSense is a desktop application that runs on your own computer, so most of this
						policy describes data we never receive. The rest describes this website, which is an
						ordinary website and behaves like one. This policy is written by SurfSense, the
						publisher of the SurfSense desktop application and the operator of surfsense.com, and we
						are the data controller for the processing described in section 4. You can reach us at
						any time at <a href="mailto:rohan@surfsense.com">rohan@surfsense.com</a>.
					</p>

					<h2>1. What this policy covers</h2>
					<p>
						This policy covers the SurfSense desktop application for Windows, macOS and Linux, and
						this website at www.surfsense.com including its documentation, pricing, licence and free
						chat pages. It applies from the date above.
					</p>
					<p>
						It does not cover the separately licensed scraper plugins beyond what section 4.4 says
						about them, third-party model providers you choose to connect, or other people's
						websites that we link to. Each of those is governed by its own terms. If you run your
						own copy of the open source server components, you are the operator of that deployment
						and this policy does not describe it.
					</p>
					<p>
						Our previously hosted web application is being retired. If you used it, the export and
						deletion arrangements on <Link href="/sunset">the sunset page</Link> apply to that data
						rather than this policy.
					</p>

					<h2>2. The short version</h2>
					<p>
						The desktop app has no account, no sign-in and no telemetry of any kind. Your documents,
						chats and search index are files on your disk, we never receive them, and there is
						therefore nothing for us to disclose, sell, leak or lose. This website counts page views
						using analytics that is on by default and that you can block, and carries no
						advertising. We do not sell personal data, we do not share it for advertising, and we do
						not build profiles for anyone else.
					</p>

					<h2>3. The desktop application</h2>

					<h3>3.1 What stays on your computer</h3>
					<p>
						When you add a document, the app parses it, splits it into passages and builds a search
						index entirely on your machine. The result is written to a database file in your user
						folder, under <code>~/.surfsense</code>. Your chats, your search index, your settings
						and everything Studio generates from your sources live in that same folder. Deleting the
						folder deletes all of it, and no copy exists anywhere else unless you made one.
					</p>
					<p>
						There is no account and no sign-in, so nothing you do in the app is attached to an
						identity we hold. The only identity involved is your operating system user.
					</p>

					<h3>3.2 What the app can send, and when</h3>
					<p>
						The app can reach three kinds of destination. Each one is listed in Settings under
						Network, each one is switched off until you enable it, and switching one off blocks the
						call rather than hiding it.
					</p>
					<ul>
						<li>
							<strong>Update checks, to github.com.</strong> Sends your IP address and the version
							you are running, so the app can tell whether a newer release exists. Disabled until
							you enable it, and you can check manually instead.
						</li>
						<li>
							<strong>Model downloads, to registry.ollama.ai and huggingface.co.</strong> Sends the
							name of the model you asked to download, along with your IP address as any download
							does. No document content and no prompts are involved.
						</li>
						<li>
							<strong>A model provider you configure.</strong> Sends your prompts, excerpts of the
							documents your answer is drawn from, and the API key you supplied, to whichever host
							you entered.
						</li>
					</ul>
					<p>
						The third one deserves emphasis. If you connect a model that you do not run yourself,
						the content of your questions and parts of your documents leave your machine and are
						handled by that provider under their privacy policy and their retention rules, not ours.
						We are not a party to that request, we do not proxy it, and we never see it. Choose a
						local model if you would prefer that nothing leaves at all: document parsing, retrieval,
						chat, image generation and the podcast voice can all run on your own hardware with every
						destination above disabled.
					</p>

					<h3>3.3 No telemetry, and an offline licence check</h3>
					<p>
						The desktop app contains no analytics, no usage tracking, no crash reporting and no
						advertising identifiers. This is why there is no telemetry setting to turn off: there is
						nothing to turn off. We cannot tell how many documents you have, which features you use,
						whether the app crashed, or whether you ever opened it.
					</p>
					<p>
						If you buy a licence, it is verified on your own machine. The app checks the licence
						file's cryptographic signature against a public key compiled into the build. It does not
						contact a licence server, it does not phone home periodically, and it does not compute
						or transmit a device fingerprint.
					</p>

					<h3>3.4 What is encrypted, and what is not</h3>
					<p>
						Your provider API keys are encrypted before they are stored, with the encryption key
						held by your operating system's keychain through Electron's <code>safeStorage</code>. On
						Linux, where no keyring is available, that mechanism falls back to weaker local
						protection.
					</p>
					<p>
						Your documents, chats and search index are <em>not</em> encrypted at rest. They are
						ordinary files with ordinary file permissions. If you need them encrypted, use your
						operating system's full-disk encryption, such as BitLocker on Windows, FileVault on
						macOS or LUKS on Linux, or keep the folder on an encrypted volume. Anyone with access to
						your user account or an unencrypted backup of your disk can read them.
					</p>
					<p>
						Whether any of this satisfies a particular regulation depends on the controls you put
						around it, and those are yours to establish. No software carries compliance as a
						property on its own. What we can tell you is narrower and checkable: where the files
						are, what can leave, and that we hold no copy.
					</p>

					<h2>4. This website</h2>

					<h3>4.1 Analytics</h3>
					<p>
						We use PostHog to understand how the site is used. It records the pages you open, when
						you leave them, the address that referred you, whether you arrived with a referral code
						in the link, and the technical details every browser sends: your IP address, from which
						an approximate location is derived, along with your browser, operating system and device
						type. Requests are sent through <code>assets.surfsense.com</code>, a proxy we operate,
						rather than directly to PostHog. PostHog assigns your browser a pseudonymous identifier
						so that repeat visits are counted as one visitor rather than several.
					</p>
					<p>
						Analytics is enabled by default and we do not display a consent banner. If you would
						rather not be counted, you can stop it: a content blocker, a tracker-blocking browser,
						or a browser setting that refuses third-party storage will all prevent it, and every
						page continues to work normally when you do. We do not currently detect the Global
						Privacy Control signal or Do Not Track headers, so please do not rely on either with us.
					</p>

					<h3>4.2 Cookies and browser storage</h3>
					<p>We set the following, and nothing for advertising:</p>
					<ul>
						<li>
							<strong>A session cookie</strong>, if you sign in, to keep you signed in. Strictly
							necessary; blocking it prevents signing in.
						</li>
						<li>
							<strong>Preference cookies and local storage</strong>, remembering your locale, theme,
							sidebar width, panel state and which notices you have dismissed, so the site looks the
							same when you return.
						</li>
						<li>
							<strong>PostHog cookies</strong>, holding the pseudonymous visitor identifier
							described in section 4.1.
						</li>
						<li>
							<strong>Cloudflare Turnstile</strong>, set by Cloudflare on the free chat pages to
							distinguish a person from a script.
						</li>
					</ul>
					<p>
						Your browser controls all of it. Blocking everything except the session cookie costs you
						nothing but your saved preferences.
					</p>

					<h3>4.3 Free chat without an account</h3>
					<p>
						The free chat pages let you talk to a model without registering. Those conversations are
						not stored against any user account. The prompts you type are passed to the model
						provider serving that model so it can answer you, which means you should not paste
						anything confidential into a page that is explicitly free and anonymous. Cloudflare
						Turnstile protects those pages from automated abuse, and Cloudflare receives the
						technical signals it needs to make that determination.
					</p>

					<h3>4.4 Licences, payment and the scraper plugins</h3>
					<p>
						If you request a trial licence or ask us to resend one, we receive the email address you
						type and use it to send you that licence and to answer support about it. Paid licences
						are sold through Stripe. Stripe processes your payment, receives the billing details you
						give them, and keeps the transaction records that tax and accounting law require them to
						keep. Your card details never reach us and we cannot see them.
					</p>
					<p>
						The scraper plugins, which a licence unlocks, run against a service we operate. When you
						ask a plugin to fetch something, that service receives the request and its target so it
						can carry out the fetch, along with the licence identifying the request. We keep
						operational records of that usage in order to enforce rate limits, detect abuse and bill
						correctly.
					</p>

					<h3>4.5 Hosting and server logs</h3>
					<p>
						This site is hosted on Vercel and fronted by Cloudflare. Both keep short-lived server
						and edge logs containing IP addresses, requested URLs, timestamps and user agents, which
						is how any web server works and is necessary to serve pages, absorb attacks and diagnose
						faults.
					</p>

					<h2>5. Why we are allowed to process it</h2>
					<p>
						Where the GDPR or UK GDPR applies, we rely on these legal bases. We do not process
						special category data, and we do not use your data for automated decision-making or
						profiling that has a legal or similarly significant effect on you.
					</p>
					<ul>
						<li>
							<strong>Contract.</strong> Sending you a licence you asked for, taking payment,
							providing the plugin service and supporting it.
						</li>
						<li>
							<strong>Legitimate interests.</strong> Keeping the site available and secure,
							preventing abuse of free and trial offers, and understanding aggregate usage so we can
							improve the product. We have weighed these against your interests, which is why
							analytics is limited to what section 4.1 lists and is straightforward to block.
						</li>
						<li>
							<strong>Legal obligation.</strong> Keeping tax, accounting and payment records, and
							responding to lawful requests.
						</li>
						<li>
							<strong>Consent.</strong> Where we ask for it, such as if you opt in to product
							emails. You can withdraw it at any time.
						</li>
					</ul>

					<h2>6. Who else sees it</h2>
					<p>
						We do not sell personal data and we do not share it for cross-context behavioural
						advertising. We use a small number of service providers, each processing data only as
						needed to do their job for us and bound by their own terms:
					</p>
					<ul>
						<li>
							<strong>Vercel</strong> and <strong>Cloudflare</strong>, for hosting, content delivery
							and bot protection.
						</li>
						<li>
							<strong>PostHog</strong>, for the product analytics described in section 4.1.
						</li>
						<li>
							<strong>Stripe</strong>, for payments.
						</li>
						<li>
							<strong>Our email provider</strong>, to deliver licence and support email.
						</li>
					</ul>
					<p>
						We may also disclose data where the law requires it, to enforce our terms, or to protect
						our rights or someone's safety. If our business is ever transferred, data may transfer
						with it, and we will say so here before that takes effect.
					</p>
					<p>
						Model providers you connect yourself are not our processors. You choose them and your
						relationship is with them directly.
					</p>

					<h2>7. Where it goes</h2>
					<p>
						The providers listed above are largely based in the United States, so personal data
						relating to this website may be transferred outside the United Kingdom and the European
						Economic Area. Where those transfers are subject to UK or EU data protection law, they
						rely on the European Commission's Standard Contractual Clauses, the UK Addendum or an
						applicable adequacy decision, as offered by each provider. Data handled entirely inside
						the desktop app is not transferred anywhere, because it never leaves your computer.
					</p>

					<h2>8. How long we keep it</h2>
					<p>
						Analytics data is retained by PostHog for its configured retention period and then
						deleted or aggregated beyond recognition. Email addresses used for licences are kept for
						as long as the licence is live and for a reasonable period afterwards, so we can resend
						it and honour support. Payment and invoice records are kept by Stripe and by us for the
						period tax law requires, commonly six to seven years. Server and edge logs are
						short-lived, typically days to a few weeks. Plugin usage records are kept only as long
						as needed for billing, rate limiting and abuse investigation. Aggregated figures that
						can no longer identify anyone may be kept indefinitely.
					</p>
					<p>
						Anything inside the desktop app is kept for exactly as long as you keep it, because we
						are not holding it.
					</p>

					<h2>9. Security</h2>
					<p>
						We use measures appropriate to a small team running a mostly local product: encryption
						in transit for the website and the plugin service, access limited to the people who need
						it, reliance on established providers for payments and hosting rather than handling card
						data ourselves, and a public codebase that anyone can audit. The strongest protection
						here is structural: the data most people care about never reaches us.
					</p>
					<p>
						No service can promise perfect security, and we do not. If we ever suffer a breach
						affecting personal data we hold, we will notify the relevant authority and affected
						people as the law requires.
					</p>

					<h2>10. Your rights</h2>
					<p>
						For anything you do in the desktop app there is nothing for us to give you or delete,
						because we never had it. Your copy is the only copy, and you can export, move or destroy
						it without involving us.
					</p>
					<p>
						For this website, and wherever the GDPR, UK GDPR or a comparable law applies, you can
						ask us to give you a copy of the personal data we hold about you, correct it, delete it,
						restrict or object to how we use it, provide it in a portable format, or withdraw
						consent where consent is what we relied on. Email us and we will act on it without undue
						delay and within the period the law allows. We may need to verify who you are first, and
						we will not charge you or treat you differently for asking. If you are unhappy with our
						answer, you can complain to your national data protection authority; in the United
						Kingdom that is the Information Commissioner's Office.
					</p>
					<p>
						If you are a California resident, the CCPA as amended by the CPRA gives you the right to
						know what we collect and why, to delete it, to correct it, and not to be discriminated
						against for exercising those rights. The categories we collect for this website are
						identifiers, internet activity and commerce information, as described in section 4,
						collected for the purposes in section 5. We do not sell personal information and we do
						not share it for cross-context behavioural advertising, so there is no opt-out of sale
						or sharing to offer. You may use an authorised agent to make a request on your behalf.
						Residents of other US states with comprehensive privacy laws have equivalent rights and
						can use the same email address.
					</p>

					<h2>11. Children</h2>
					<p>
						SurfSense is not designed for or directed at children, and is not intended for anyone
						under 13, or under 16 in the European Economic Area and the United Kingdom. We do not
						knowingly collect personal data from children. If you believe a child has sent us
						something, email us and we will delete it.
					</p>

					<h2>12. Changes to this policy</h2>
					<p>
						When something material changes we update the date at the top of this page, and for a
						change that meaningfully affects people holding a paid licence we will email the address
						on that licence. Because the application is open source, you do not have to take this
						document on trust: the code that reads your files, the list of destinations the app can
						reach and the analytics configuration for this site are all public and reviewable.
					</p>

					<h2>13. Contact</h2>
					<p>
						Questions about this policy, or a request about your data, go to{" "}
						<a href="mailto:rohan@surfsense.com">rohan@surfsense.com</a> and a person will read it.
						Our <Link href="/terms">Terms of Service</Link> cover the rest of the relationship.
					</p>
				</div>
			</div>
		</div>
	);
}
