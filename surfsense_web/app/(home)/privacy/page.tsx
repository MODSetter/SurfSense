import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
	title: "Privacy Policy | SurfSense",
	description:
		"Privacy Policy for SurfSense. Learn how we collect, use, and protect your data, and how third-party services such as Google AdSense use cookies on our site.",
	alternates: {
		canonical: "https://www.surfsense.com/privacy",
	},
};

/**
 * Update this date whenever you make a material change to the policy. Keeping
 * it as a static constant (rather than `new Date()`) avoids hydration
 * mismatches and makes the policy look professionally maintained to reviewers
 * (including AdSense reviewers).
 */
const LAST_UPDATED = "May 21, 2026";

export default function PrivacyPolicy() {
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="text-4xl font-bold mb-8">Privacy Policy</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">Last updated: {LAST_UPDATED}</p>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">1. Introduction</h2>
					<p>
						Welcome to SurfSense ("SurfSense", "we", "us", or "our"). We operate the website at{" "}
						<a href="https://www.surfsense.com">www.surfsense.com</a> and the SurfSense application
						(collectively, the "Service"). We respect your privacy and are committed to protecting
						your personal data. This Privacy Policy explains what data we collect, how we use it,
						who we share it with, and the rights you have over your data.
					</p>
					<p className="mt-4">
						By accessing or using the Service, you acknowledge that you have read and understood
						this Privacy Policy. If you do not agree with our policies and practices, do not use
						the Service. We may modify this policy from time to time; material changes will be
						reflected by updating the "Last updated" date above.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">2. Data We Collect</h2>
					<p>We collect the following categories of personal data:</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							<strong>Identity Data</strong> includes first name, last name, username, or similar
							identifier you provide when registering for an account.
						</li>
						<li>
							<strong>Contact Data</strong> includes email address and any contact information you
							provide when reaching out to support or completing the contact form.
						</li>
						<li>
							<strong>Account and Authentication Data</strong> includes hashed passwords (for local
							authentication) and OAuth tokens issued by identity providers such as Google when you
							sign in with a third-party account.
						</li>
						<li>
							<strong>Chat and Knowledge Base Data</strong> includes the messages, prompts,
							documents, and notes you submit through the Service when signed in. Anonymous chat
							sessions on our free pages are not stored in any user-linked database.
						</li>
						<li>
							<strong>Document and Integration Data</strong> includes content from files you upload
							and data fetched from third-party services you connect (such as Slack, Google Drive,
							Notion, Confluence, GitHub, and others) under the scopes you authorize.
						</li>
						<li>
							<strong>Billing Data</strong> includes information necessary to process payments
							(such as transaction identifiers and credit balances). Card details are handled by
							our payment processor and are not stored on our servers.
						</li>
						<li>
							<strong>Technical Data</strong> includes internet protocol (IP) address, browser type
							and version, time zone, operating system, device identifiers, and other technology
							identifiers from the devices you use to access the Service.
						</li>
						<li>
							<strong>Usage Data</strong> includes information about how you interact with the
							Service, such as pages visited, features used, referring URLs, and timestamps.
						</li>
						<li>
							<strong>Advertising Data</strong> includes cookie identifiers, ad interaction data,
							and pseudonymous identifiers set by Google AdSense and its partners on pages that
							serve ads. See Section 5 for details.
						</li>
						<li>
							<strong>Marketing and Communications Data</strong> includes your preferences for
							receiving marketing communications from us.
						</li>
						<li>
							<strong>Aggregated Data</strong> derived from any of the above and stripped of
							identifiers. Aggregated data is not considered personal data under most laws.
						</li>
					</ul>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">3. How We Use Your Data</h2>
					<p>We use your personal data only where we have a lawful basis to do so, including:</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							To create and manage your account, authenticate you, and provide the Service you have
							requested.
						</li>
						<li>
							To process payments, manage your credit balance, and prevent fraud and abuse of the
							Service.
						</li>
						<li>
							To answer your queries by sending prompts and content you submit to large language
							model providers (see Section 8) and return the responses to you.
						</li>
						<li>
							To synchronize data from third-party services you have explicitly connected (such as
							Slack, Google Drive, or Notion) so that the Service can search and reference that
							content on your behalf.
						</li>
						<li>
							To monitor, analyze, and improve the Service, diagnose issues, and detect security
							incidents.
						</li>
						<li>
							To communicate with you about product updates, security notices, support requests,
							and (with your consent where required) marketing.
						</li>
						<li>
							To serve and measure advertising on pages where ads are shown (currently, our free
							public pages). See Section 5 for details.
						</li>
						<li>To comply with legal obligations and enforce our Terms of Service.</li>
					</ul>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">4. Cookies and Tracking Technologies</h2>
					<p>
						We and our partners use cookies, local storage, and similar technologies to operate the
						Service, remember your preferences, measure usage, and serve advertising. The
						categories include:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							<strong>Strictly necessary</strong> cookies and storage required for authentication,
							session management, security (including CAPTCHA), and core functionality.
						</li>
						<li>
							<strong>Preference</strong> cookies and storage that remember choices such as theme,
							language, and onboarding state.
						</li>
						<li>
							<strong>Analytics</strong> cookies that help us understand how the Service is used so
							we can improve it. We use PostHog for product analytics.
						</li>
						<li>
							<strong>Advertising</strong> cookies set by Google AdSense and its partners on pages
							that serve ads. These cookies are used to deliver relevant ads, measure ad
							performance, and limit how often an ad is shown to the same user. See Section 5.
						</li>
					</ul>
					<p className="mt-4">
						You can control cookies through your browser settings. Blocking strictly necessary
						cookies will prevent the Service from functioning correctly. Where required by law, we
						request your consent before setting non-essential cookies.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">5. Advertising and Google AdSense</h2>
					<p>
						Our free public pages (currently <Link href="/free">www.surfsense.com/free</Link>) are
						supported by advertising served through Google AdSense, a service provided by Google
						LLC.
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							Google, as a third-party vendor, uses cookies (including the DoubleClick DART
							cookie) to serve ads to you based on your visits to our Service and other websites
							on the Internet.
						</li>
						<li>
							Google's use of advertising cookies enables it and its partners to serve ads to you
							based on your visit to our Service and/or other sites on the Internet.
						</li>
						<li>
							You may opt out of personalized advertising by visiting{" "}
							<a href="https://www.google.com/settings/ads">Google Ads Settings</a>. You may also
							opt out of some third-party vendors' use of cookies for personalized advertising at{" "}
							<a href="https://www.aboutads.info/choices/">www.aboutads.info/choices</a> (US) or{" "}
							<a href="https://www.youronlinechoices.com/">youronlinechoices.com</a> (EU).
						</li>
						<li>
							For users in the European Economic Area, the United Kingdom, and Switzerland, we
							use a Google-certified Consent Management Platform to obtain your consent for
							personalized advertising before such cookies are set. You may change or withdraw
							your consent at any time through the consent banner.
						</li>
						<li>
							We do not knowingly serve personalized advertising to children. See Section 11.
						</li>
					</ul>
					<p className="mt-4">
						For more information about how Google uses data when you use our Service, see{" "}
						<a href="https://policies.google.com/technologies/partner-sites">
							How Google uses information from sites or apps that use our services
						</a>
						.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">6. Data Security</h2>
					<p>
						We implement technical and organizational measures designed to protect your personal
						data against accidental loss, unauthorized access, alteration, and disclosure. Access
						to personal data is limited to personnel who need it to operate the Service.
					</p>
					<p className="mt-4">
						No system can be guaranteed to be fully secure. We cannot guarantee that personal data
						transmitted to or stored by the Service will be free from unauthorized access. You are
						responsible for keeping your account credentials confidential.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">7. Data Retention</h2>
					<p>
						We retain personal data only for as long as necessary to provide the Service and to
						comply with our legal, accounting, and reporting obligations. Account data is retained
						for the life of your account; you can request deletion at any time. Aggregated data
						that no longer identifies you may be retained indefinitely for analytics and product
						improvement purposes. Anonymous chat sessions on our free pages are not retained in
						any user-linked database.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">8. Third-Party Services</h2>
					<p>
						We rely on the following categories of third-party processors and providers to operate
						the Service. Each is bound by its own privacy policy, which we encourage you to
						review:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							<strong>Authentication</strong>: Google (OAuth sign-in).
						</li>
						<li>
							<strong>Hosting and infrastructure</strong>: Vercel, Cloudflare (CAPTCHA via
							Cloudflare Turnstile, DNS, and edge protection).
						</li>
						<li>
							<strong>Analytics</strong>: PostHog (product analytics).
						</li>
						<li>
							<strong>Advertising</strong>: Google AdSense (see Section 5).
						</li>
						<li>
							<strong>Large language model providers</strong>: OpenAI, Anthropic, Google, and
							other LLM providers process the prompts and content you submit to the Service in
							order to generate responses.
						</li>
						<li>
							<strong>Integration providers</strong>: When you explicitly connect a third-party
							service (such as Slack, Google Drive, Notion, Confluence, GitHub, Jira, Linear, or
							similar), data is exchanged with that service under the scopes you authorize.
						</li>
					</ul>
					<p className="mt-4">
						We do not sell personal data to third parties. We share data with the providers above
						only to the extent needed to operate the Service.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">
						9. Your Legal Rights (Including GDPR)
					</h2>
					<p>
						Subject to applicable law, you have the following rights in relation to your personal
						data:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>The right to access the personal data we hold about you.</li>
						<li>The right to request correction of inaccurate or incomplete data.</li>
						<li>The right to request erasure of your personal data ("right to be forgotten").</li>
						<li>The right to object to or restrict certain processing of your data.</li>
						<li>The right to data portability (to receive your data in a portable format).</li>
						<li>
							The right to withdraw consent at any time where we rely on consent to process your
							data (such as for advertising cookies in the EEA, UK, and Switzerland).
						</li>
						<li>
							The right to lodge a complaint with your local supervisory authority if you believe
							our processing of your data infringes applicable law.
						</li>
					</ul>
					<p className="mt-4">
						To exercise any of these rights, please contact us using the details in Section 13. We
						may need to verify your identity before responding to your request.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">10. California Residents (CCPA / CPRA)</h2>
					<p>
						If you are a California resident, you have additional rights under the California
						Consumer Privacy Act (as amended by the CPRA), including:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							The right to know what categories of personal information we have collected about
							you and how it is used and shared.
						</li>
						<li>The right to delete personal information we have collected from you.</li>
						<li>The right to correct inaccurate personal information.</li>
						<li>
							The right to opt out of the "sale" or "sharing" of personal information for
							cross-context behavioral advertising. We do not sell personal data; however,
							advertising cookies set by Google AdSense may be considered "sharing" under
							California law. To opt out, you can use the consent controls described in Section 5
							or enable a Global Privacy Control (GPC) signal in your browser, which we honor.
						</li>
						<li>The right not to be discriminated against for exercising your privacy rights.</li>
					</ul>
					<p className="mt-4">
						To exercise your CCPA rights, please contact us using the details in Section 13.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">11. Children's Privacy</h2>
					<p>
						The Service is not directed to children under 13 (or under 16 in the EEA, UK, and
						Switzerland). We do not knowingly collect personal data from children. If you believe
						a child has provided us with personal data, please contact us and we will take steps
						to delete it. We do not knowingly serve personalized advertising to children.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">12. Changes to This Policy</h2>
					<p>
						We may update this Privacy Policy from time to time to reflect changes in our
						practices, technology, legal requirements, or for other operational reasons. When we
						make material changes, we will update the "Last updated" date at the top of this page
						and, where appropriate, provide additional notice (such as an in-product notification
						or email). Your continued use of the Service after the updated policy becomes
						effective constitutes your acceptance of the revised policy.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">13. Contact Us</h2>
					<p>
						If you have questions about this Privacy Policy or our privacy practices, or if you
						want to exercise any of your rights, please contact us at:
					</p>
					<p className="mt-2">
						<strong>Email:</strong>{" "}
						<a href="mailto:rohan@surfsense.com">rohan@surfsense.com</a>
					</p>
				</section>
			</div>
		</div>
	);
}
