import type { Metadata } from "next";
import Link from "next/link";
import { LegalDraftNotice } from "@/components/site/legal-draft-notice";
import { EMAIL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";

/**
 * Privacy Policy. Plain long-form prose, laid out like a blog post: the padded `max-w-3xl`
 * + Tailwind `prose` wrapper is copied from `app/(home)/blog/[slug]/page.tsx`.
 * `app/(home)/layout.tsx` supplies the light palette, the navigation and the footer.
 *
 * MAINTAINER REVIEW NEEDED BEFORE THIS SHIPS. Redrafted on 21 Nov 2026 for the free app run
 * by its maintainer as an individual, after SurfSense Inc. winds down on 27 Nov 2026. What
 * changed from the 10 Nov 2026 version:
 *
 * - **The controller** is Rohan Verma, an individual.
 * - **Gone:** licences, trials, payments (Stripe), the licensing system (Keygen), licence and
 *   support email, the licence server at api.surfsense.com, SurfSense's scraper plugins and
 *   their usage counts, the hosted web search at searxng.surfsense.com, the free chat pages
 *   and Cloudflare Turnstile, and the trial and checkout events with their channel tag.
 * - **Kept and still described:** the desktop app's opt-in usage statistics
 *   (usage.surfsense.com), the update checks older versions make through
 *   updates.surfsense.com, the website's PostHog analytics, the server-side download count,
 *   and the legacy 0.0.x app's own events.
 * - **New:** from 2.4.0 the app checks for updates on GitHub directly; plugins.surfsense.com
 *   is static files on Vercel; api.surfsense.com only answers the legacy app's start-up check.
 * - **Telemetry revision:** dev's page said 2.3.2 for the days-since-install ranges; that
 *   was never released on its own, so it now says 2.4.0.
 * - The `[DATE]` in section 8 is the day SurfSense Inc.'s licence and purchase records are
 *   deleted, the date the announcement names. Fill it in, then set `REVIEWED` to true.
 *
 * Three claims stay deliberately hedged because the obvious phrasing would be false: the
 * local database is not encrypted at rest (only API keys are, through `safeStorage`), the
 * Linux keychain fallback is weaker, and remote models receive document content.
 */

const canonicalUrl = "https://www.surfsense.com/privacy";

const metaTitle = "Privacy Policy | SurfSense";
const metaDescription =
	"What SurfSense collects and what it does not. The free desktop app has no account, sends usage statistics only if you opt in and never with an identifier, and your documents never reach me.";

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
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense privacy policy" }],
	},
};

/** Set to true once the maintainer has reviewed this redraft; until then the page says so. */
const REVIEWED = false;

/**
 * Update whenever a material change lands. A static constant rather than `new Date()`: a
 * render-time date causes a hydration mismatch and tells every reader the document changed.
 */
const LAST_UPDATED = "November 27, 2026";

/** Matches the `prose` treatment used for blog posts. */
const PROSE =
	"prose max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-headings:tracking-tight prose-a:no-underline";

export default function PrivacyPolicy() {
	return (
		<div className="pt-16 pb-20">
			<div className="mx-auto max-w-3xl">
				<div className="mb-10 space-y-4 text-center">
					<h1 className={siteText.h2}>Privacy Policy</h1>
					<p className="text-muted-foreground text-sm">Last updated: {LAST_UPDATED}</p>
				</div>

				<LegalDraftNotice reviewed={REVIEWED} />

				<div className={PROSE}>
					<p>
						SurfSense is a free desktop application that runs on your own computer, so most of this
						policy describes data I never receive. The rest describes this website and the few files
						and routes it serves to the application. SurfSense is maintained by Rohan Verma, an
						individual ("I", "me"), who operates surfsense.com and is the data controller for the
						processing in sections 4 and 5. Until 27 November 2026 SurfSense was published by
						SurfSense Inc., which has wound down. You can reach me at{" "}
						<a href={`mailto:${EMAIL}`}>{EMAIL}</a>.
					</p>

					<h2>1. What this policy covers</h2>
					<p>
						This policy covers the SurfSense desktop application for Windows, macOS and Linux, and
						this website at www.surfsense.com with the hosts it serves the application from:
						updates.surfsense.com, usage.surfsense.com, plugins.surfsense.com and api.surfsense.com.
						It applies from the date above.
					</p>
					<p>
						It does not cover third-party model providers, plugins, MCP servers or search servers
						you choose to connect, or other people's websites I link to. Each of those is governed
						by its own terms. If you run your own copy of SurfSense's server components, you are the
						operator of that deployment and this policy does not describe it.
					</p>

					<h2>2. The short version</h2>
					<p>
						The desktop app has no account, no sign-in and no licence, and sends no usage statistics
						unless you opt in, and even then only counts in ranges and the app's version, platform
						and language, with no identifier. Your documents, chats and search index are files on
						your disk; I never receive them, so there is nothing for me to disclose, sell, leak or
						lose. This website counts page views with analytics that is on by default and that you
						can block, and carries no advertising. Nothing is sold, so no payment data is collected.
						I do not sell personal data, share it for advertising, or build profiles for anyone.
					</p>

					<h2>3. The desktop application</h2>

					<h3>3.1 What stays on your computer</h3>
					<p>
						When you add a document, the app parses it, splits it into passages and builds a search
						index entirely on your machine. The result is written to a database file in your user
						folder, under <code>~/.surfsense</code>. Your chats, your search index, your settings
						and everything Studio and the jobs generate from your sources live in that same folder.
						Deleting the folder deletes all of it, and no copy exists anywhere else unless you made
						one.
					</p>
					<p>
						There is no account and no sign-in, so nothing you do in the app is attached to an
						identity I hold. The only identity involved is your operating system user.
					</p>

					<h3>3.2 What the app can send, and when</h3>
					<p>
						The app can reach the destinations below. Each one is switched off until you allow it,
						when the app first starts or under Network in Settings, and switching one off there
						blocks the call rather than hiding it.
					</p>
					<ul>
						<li>
							<strong>Update checks, to github.com.</strong> Once a day and whenever you click Check
							now, the app asks GitHub whether a newer release exists, and downloads it from GitHub,
							whose download host, githubusercontent.com, also sees your IP address. From version
							2.4.0 the app reads GitHub directly, sending your IP address and a user agent, and no
							identifier and no cookies. Versions 2.2.4 to 2.3.x ask updates.surfsense.com first,
							sending your IP address, a user agent that says only SurfSense, the app's version,
							your platform (such as win32-x64) and your operating system (such as windows-11); that
							route passes GitHub's release file back and counts the check, as section 3.3
							describes, and the app falls back to GitHub if it fails. Versions up to 2.2.3 ask
							github.com alone, identifying themselves as electron-builder and sending a random
							identifier the update library creates for staged rollouts. Off until you turn it on,
							and an administrator can turn it off, or point it at their own update server, for
							every user of a computer.
						</li>
						<li>
							<strong>Usage statistics, to usage.surfsense.com.</strong> Only if you opt in: one
							report a day, and, from version 2.2.5, during the install's first week one more each
							time setup reaches a new step (at most four more). A report that does not get through
							is tried again later. Each report sends the app's version, platform, operating system
							and interface language, the week the app was installed, why it was sent (the day's
							report or a new setup step), and whether this is its first daily report ever, this
							week and this month. From version 2.4.0 it also says how many days ago the app was
							installed, in ranges such as 2-3, and whether this is its first daily report in that
							range. Once a week it adds counts in ranges, such as 10-49, for the past seven days:
							chat turns, agent turns, whether a local or a remote model answered, the documents in
							your library, Studio outputs, plugin calls, and how far setup got, and, from version
							2.4.0, on how many of the 7 and the 28 days before it SurfSense was used. During the
							first week every report carries those counts, for the time since installation. The
							first daily report adds your computer's memory, graphics card maker and graphics
							memory, also in ranges, and whether SurfSense's model runtime can use the graphics
							card; during the first week that is sent again only while part of it is unknown, and
							only when it changed. It never sends documents, prompts, file names, model names,
							model hosts or an identifier. Settings shows the exact next daily report and the last
							report sent.
						</li>
						<li>
							<strong>Plugins, to plugins.surfsense.com.</strong> Fetching the list of third-party
							plugins, and their icons, sends your IP address and nothing else. These are static
							files on the same hosting as this website. Versions before 2.4.0 that still try
							SurfSense's own plugins, which closed on 27 November 2026, send those requests there
							too, with the licence key such a version holds; they are answered that the plugin no
							longer exists, and I keep no record of the key.
						</li>
						<li>
							<strong>Web search, to a server you choose.</strong> From version 2.4.0 web search is
							off until you enter your own SearXNG server in Settings. A search in Add from the web
							or by the agent then sends what you search for, and your IP address, to that server
							only. A search the agent writes can carry words from your chats or documents, but
							nothing else from them is sent. I receive none of it.
						</li>
						<li>
							<strong>Model search and downloads, to huggingface.co.</strong> Searching sends what
							you type into the model search as you type it. Downloading sends the name of the model
							you chose. Both send your IP address, as any request does. No document content and no
							prompts are involved.
						</li>
						<li>
							<strong>Pages and videos you or the agent read, to each site.</strong> Adding a link
							in Sources, or the agent reading one, reads that page from its own site on your own
							connection, as your browser would: the site receives the page's address and your IP
							address. The agent chooses the addresses it reads, so an address can carry words from
							your chats or documents, such as a search term, but nothing else from them is sent. A
							YouTube video's transcript is read the same way, from www.youtube.com. The app asks
							before it first reads from a site, including one a page sends it on to.
						</li>
						<li>
							<strong>The Office pack, from downloadarchive.documentfoundation.org.</strong> Turning
							on Office support downloads The Document Foundation's LibreOffice build, sending the
							file's name and your IP address. That host redirects the download to one of its
							mirrors, which also sees your IP address.
						</li>
						<li>
							<strong>A plugin server you connect.</strong> A third-party plugin's server, and its
							sign-in server if it has one, receives what each tool you allow is sent, along with
							your IP address, never your whole conversation. Signing in to one goes through a page
							at plugins.surfsense.com that runs in your browser and hands the result straight to
							the app on your computer; that page is a static file and I receive nothing from it.
						</li>
						<li>
							<strong>A model provider you configure.</strong> Sends your prompts, excerpts of the
							documents your answer is drawn from, and the API key you supplied, to whichever host
							you entered.
						</li>
					</ul>
					<p>
						The last one deserves emphasis. If you connect a model that you do not run yourself, the
						content of your questions and parts of your documents leave your machine and are handled
						by that provider under their privacy policy and retention rules, not mine. I am not a
						party to that request, I do not proxy it, and I never see it. Running a job is the same:
						the app reads your documents on your computer and sends them only to the models you
						chose for the job. Choose a local model if you would prefer that nothing leaves:
						document parsing, retrieval, chat, image generation and the podcast voice can all run on
						your own hardware with every destination above disabled. One thing these switches do not
						hold: the scripts a model writes to build documents, for Studio's Office formats and for
						the agent, run on your computer and can open connections of their own.
					</p>

					<h3>3.3 Usage statistics</h3>
					<p>
						The desktop app contains no analytics library, no crash reporting and no advertising
						identifiers, and sends no usage statistics unless you opt in. With usage statistics on,
						I receive the counts in ranges that section 3.2 lists. Versions 2.2.4 to 2.3.x that
						check for updates through updates.surfsense.com are also counted there each day, with
						their versions, platforms and countries. Neither carries documents, prompts, file names,
						model hosts or an identifier, so I cannot see what you did in the app, and no identifier
						ties one install's reports together, although an uncommon combination of version,
						platform, language, install week or age and country could single one install out. Each
						request's IP address is used by the hosting provider to route it and to derive a
						country; its logs hold it for the short time sections 4.3 and 8 describe, and only the
						country is kept. You can turn usage statistics off in Settings at any time, set{" "}
						<code>DO_NOT_TRACK=1</code> to keep them off, or have an administrator turn them off for
						a whole computer.
					</p>
					<p>
						From version 2.4.0 the app has no licence check of any kind, and it does not compute or
						transmit a device fingerprint.
					</p>
					<p>
						The retired 0.0.x desktop app, which wrapped SurfSense Inc.'s former hosted service,
						still sends events to analytics when it starts, updates and quits: its version,
						operating system, processor architecture, whether it started at login, and a machine
						identifier. At startup it also asks api.surfsense.com whether the hosted service is
						still open, which now answers that it has closed and points the app to a page for
						getting the new one. Those events are used only to count how many old installs remain.
						The current app sends no machine identifier, and nothing beyond what section 3.2 lists.
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
						around it, and those are yours to establish. What I can tell you is narrower and
						checkable: where the files are, what can leave, and that I hold no copy.
					</p>

					<h2>4. This website</h2>

					<h3>4.1 Analytics</h3>
					<p>
						This site uses PostHog to understand how it is used. In your browser it records the
						pages you open and when you leave them, the address that referred you, and any referral
						code or campaign (UTM) tags in the link. It also records which links, buttons and form
						fields you click, change or submit (the element and its visible text, never what you
						type into a field), where on a page you click, move the pointer and scroll, for
						heatmaps, how quickly pages load, and JavaScript errors your browser hits on these
						pages, with the error message and where in the code it happened. Every request carries
						the technical details any browser sends: your IP address, from which an approximate
						location is derived, and your browser, operating system and device type. Sessions are
						not recorded: session replay is switched off.
					</p>
					<p>
						These requests go to <code>assets.surfsense.com</code>, a subdomain that PostHog runs as
						a reverse proxy, rather than to PostHog's own domain. PostHog assigns your browser a
						pseudonymous identifier so that repeat visits are counted as one visitor rather than
						several. The short videos on the homepage and the pages for each profession, job and
						study tool are recorded the same way: which video started, whether it started by itself
						or because you pressed play, and whether it played to the end.
					</p>
					<p>
						Downloading an installer is counted on the server instead, without that identifier: the
						platform, where the link was (this site, the README, an email, the app, the pricing page
						or the page the old 0.0.x app opens), the version, and the country the host derives from
						your request. No IP address or browser identifier is kept with it.
					</p>
					<p>
						Analytics is enabled by default and there is no consent banner. Because the browser
						requests go to a surfsense.com subdomain, a content blocker that works from lists of
						tracking domains may not stop them. Blocking <code>assets.surfsense.com</code>, or
						turning off JavaScript for this site, does stop them, and every page keeps working when
						you do. Blocking cookies and site storage for surfsense.com stops PostHog from
						recognising a repeat visit, but not from counting the visit. The Global Privacy Control
						signal and Do Not Track headers are not currently detected, so please do not rely on
						either here.
					</p>

					<h3>4.2 Cookies and browser storage</h3>
					<p>The site sets the following, and nothing for advertising:</p>
					<ul>
						<li>
							<strong>Preference storage</strong>, remembering your theme, panel state and which
							notices you have dismissed, so the site looks the same when you return.
						</li>
						<li>
							<strong>A PostHog cookie and local storage entry</strong>, holding the pseudonymous
							visitor identifier described in section 4.1, and the first page you landed on with the
							address that referred you there.
						</li>
					</ul>
					<p>Your browser controls all of it, and blocking it costs you only your preferences.</p>

					<h3>4.3 Hosting and server logs</h3>
					<p>
						This site, and the files and routes it serves the application from the hosts in section
						1, are hosted on Vercel. Vercel keeps short-lived logs containing IP addresses,
						requested URLs, timestamps and user agents, which is how any web server works and is
						necessary to serve pages, absorb attacks and diagnose faults.
					</p>

					<h3>4.4 Email</h3>
					<p>
						If you email me, I receive your address and what you write, and use them to answer you.
						The address in this policy is a Gmail address, so Google handles that mail under its own
						terms.
					</p>

					<h2>5. Why I am allowed to process it</h2>
					<p>
						Where the GDPR or UK GDPR applies, I rely on these legal bases. I do not process special
						category data, and I do not use your data for automated decision-making or profiling
						that has a legal or similarly significant effect on you.
					</p>
					<ul>
						<li>
							<strong>Legitimate interests.</strong> Keeping the site and the files it serves
							available and secure, answering older versions' update checks, answering email, and
							understanding aggregate usage so I can improve SurfSense. I have weighed these against
							your interests, which is why analytics is limited to what section 4.1 lists and is
							straightforward to block.
						</li>
						<li>
							<strong>Consent.</strong> The desktop app's usage statistics, which are off unless you
							opt in. You can withdraw that consent at any time by turning them off in Settings or
							by setting <code>DO_NOT_TRACK=1</code>, and an administrator's policy can withdraw it
							for a whole computer. Reports already sent carry no identifier, so I cannot pick out
							yours to delete.
						</li>
						<li>
							<strong>Legal obligation.</strong> Responding to lawful requests.
						</li>
					</ul>

					<h2>6. Who else sees it</h2>
					<p>
						I do not sell personal data and do not share it for cross-context behavioural
						advertising. A small number of service providers process data only as needed to do their
						job, under their own terms:
					</p>
					<ul>
						<li>
							<strong>Vercel</strong>, for hosting this website and the hosts in section 1.
						</li>
						<li>
							<strong>PostHog</strong>, for the analytics in section 4.1 and the usage statistics in
							section 3.3.
						</li>
						<li>
							<strong>Google</strong>, for the email address in this policy.
						</li>
						<li>
							<strong>GitHub</strong>, which hosts the source code and the releases the app
							downloads, under GitHub's own privacy statement.
						</li>
					</ul>
					<p>
						I may also disclose data where the law requires it, or to protect someone's safety. If I
						hand SurfSense to another maintainer, the data in sections 3.3 and 4 may go with it, and
						I will say so here first. Model providers, plugins and search servers you connect are
						not my processors: you choose them, and your relationship is with them directly.
					</p>

					<h2>7. Where it goes</h2>
					<p>
						The providers above are largely based in the United States, so personal data relating to
						this website may be transferred outside the United Kingdom and the European Economic
						Area. Where those transfers are subject to UK or EU data protection law, they rely on
						the European Commission's Standard Contractual Clauses, the UK Addendum or an applicable
						adequacy decision, as offered by each provider. Data handled entirely inside the desktop
						app is not transferred anywhere, because it never leaves your computer.
					</p>

					<h2>8. How long it is kept</h2>
					<p>
						Analytics and usage statistics are kept by PostHog for its configured retention period
						and then deleted or aggregated beyond recognition. Server logs are short-lived,
						typically days to a few weeks. Email is kept as long as needed to answer it. Aggregated
						figures that can no longer identify anyone may be kept indefinitely.
					</p>
					<p>
						The licence and purchase records SurfSense Inc. held, the email addresses licences and
						trials were issued to, are deleted on [DATE]. Payment records stay with Stripe for the
						period tax law requires. Anything inside the desktop app is kept for exactly as long as
						you keep it, because I am not holding it.
					</p>

					<h2>9. Security</h2>
					<p>
						What this project holds is small: the website, static files and aggregate counts, with
						access limited to me, encryption in transit, and a public codebase anyone can audit. The
						strongest protection is structural: the data most people care about never reaches me. No
						service can promise perfect security, and I do not. If a breach ever affects personal
						data I hold, I will notify the relevant authority and the people affected as the law
						requires.
					</p>

					<h2>10. Your rights</h2>
					<p>
						For anything you do in the desktop app there is nothing for me to give you or delete,
						because I never had it. Your copy is the only copy.
					</p>
					<p>
						Wherever the GDPR, UK GDPR or a comparable law applies, you can ask me for a copy of the
						personal data I hold about you, to correct or delete it, to restrict or object to how I
						use it, to provide it in a portable format, or to withdraw consent where consent is what
						I relied on. Email me and I will act on it within the period the law allows. I may need
						to verify who you are first, and I will not charge you or treat you differently for
						asking. If you are unhappy with my answer, you can complain to your national data
						protection authority; in the United Kingdom that is the Information Commissioner's
						Office.
					</p>
					<p>
						If you are a California resident, the CCPA as amended by the CPRA gives you the right to
						know what is collected and why, to delete it, to correct it, and not to be discriminated
						against for exercising those rights. The categories collected for this website are
						identifiers and internet activity, as described in section 4, for the purposes in
						section 5. Personal information is not sold or shared for cross-context behavioural
						advertising, so there is no opt-out to offer. Residents of other US states with
						comprehensive privacy laws have equivalent rights and can use the same email address.
					</p>

					<h2>11. Children</h2>
					<p>
						SurfSense is not directed at children under 13, or under 16 in the European Economic
						Area and the United Kingdom, and I do not knowingly collect personal data from them. If
						you believe a child has sent me something, email me and I will delete it.
					</p>

					<h2>12. Changes to this policy</h2>
					<p>
						When something material changes, the date at the top of this page moves. Because the
						application is open source, you do not have to take this document on trust: the code
						that reads your files, the list of destinations the app can reach and the analytics
						configuration for this site are all public.
					</p>

					<h2>13. Contact</h2>
					<p>
						Questions about this policy, or a request about your data, go to{" "}
						<a href={`mailto:${EMAIL}`}>{EMAIL}</a>. The <Link href="/terms">Terms of Service</Link>{" "}
						cover the rest.
					</p>
				</div>
			</div>
		</div>
	);
}
