import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "Privacy Policy | SurfSense",
	description: "Privacy Policy for SurfSense application",
};

export default function PrivacyPolicy() {
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="text-4xl font-bold mb-8">Privacy Policy</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">Last updated: {new Date().toLocaleDateString()}</p>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">1. Introduction</h2>
					<p>
						Welcome to SurfSense. We respect your privacy and are committed to protecting your
						personal data. This privacy policy will inform you about how we look after your personal
						data when you visit our website and tell you about your privacy rights and how the law
						protects you.
					</p>
					<p className="mt-4">
						By using our services, you acknowledge that you have read and understood this Privacy
						Policy. We reserve the right to modify this policy at any time, and such modifications
						shall be effective immediately upon posting the modified policy on this website.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">2. Data We Collect</h2>
					<p>
						We may collect, use, store and transfer different kinds of personal data about you which
						we have grouped together as follows:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							<strong>Identity Data</strong> includes first name, last name, username or similar
							identifier.
						</li>
						<li>
							<strong>Contact Data</strong> includes email address and telephone numbers.
						</li>
						<li>
							<strong>Technical Data</strong> includes internet protocol (IP) address, your login
							data, browser type and version, time zone setting and location, browser plug-in types
							and versions, operating system and platform, and other technology on the devices you
							use to access this website.
						</li>
						<li>
							<strong>Usage Data</strong> includes information about how you use our website and
							services.
						</li>
						<li>
							<strong>Surf Data</strong> includes information about surf sessions, preferences, and
							equipment settings.
						</li>
						<li>
							<strong>Marketing and Communications Data</strong> includes your preferences in
							receiving marketing from us and your communication preferences.
						</li>
						<li>
							<strong>Aggregated Data</strong> which may be derived from your personal data but is
							not considered personal data as it does not directly or indirectly reveal your
							identity.
						</li>
					</ul>
					<p className="mt-4">
						We may also collect, use and share Aggregated Data such as statistical or demographic
						data for any purpose. Aggregated Data may be derived from your personal data but is not
						considered personal data in law as this data does not directly or indirectly reveal your
						identity.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">3. How We Use Your Data</h2>
					<p>
						We will only use your personal data when the law allows us to. Most commonly, we will
						use your personal data in the following circumstances:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>
							Where we need to perform the contract we are about to enter into or have entered into
							with you.
						</li>
						<li>
							Where it is necessary for our legitimate interests (or those of a third party) and
							your interests and fundamental rights do not override those interests.
						</li>
						<li>Where we need to comply with a legal obligation.</li>
						<li>
							To provide and maintain our services, including to monitor the usage of our service.
						</li>
						<li>
							To improve our services, products, marketing, and customer relationships and
							experiences.
						</li>
						<li>To communicate with you about updates, security alerts, and support messages.</li>
						<li>To provide customer support and respond to your requests or inquiries.</li>
						<li>
							For business transfers, such as in connection with a merger, sale of company assets,
							financing, or acquisition.
						</li>
					</ul>
					<p className="mt-4">
						We may use your information for marketing purposes, such as sending you information
						about our products, services, promotions, and events. You can opt-out of receiving these
						communications at any time.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">4. Data Security</h2>
					<p>
						We have put in place appropriate security measures to prevent your personal data from
						being accidentally lost, used or accessed in an unauthorized way, altered or disclosed.
						In addition, we limit access to your personal data to those employees, agents,
						contractors and other third parties who have a business need to know.
					</p>
					<p className="mt-4">
						While we implement safeguards designed to protect your information, no security system
						is impenetrable and due to the inherent nature of the Internet, we cannot guarantee that
						information, during transmission through the Internet or while stored on our systems, is
						absolutely safe from intrusion by others.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">5. Data Retention</h2>
					<p>
						We will only retain your personal data for as long as necessary to fulfill the purposes
						we collected it for, including for the purposes of satisfying any legal, accounting, or
						reporting requirements. To determine the appropriate retention period for personal data,
						we consider the amount, nature, and sensitivity of the personal data, the potential risk
						of harm from unauthorized use or disclosure of your personal data, the purposes for
						which we process your personal data and whether we can achieve those purposes through
						other means, and the applicable legal requirements.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">6. Your Legal Rights</h2>
					<p>
						Under certain circumstances, you have rights under data protection laws in relation to
						your personal data, including:
					</p>
					<ul className="list-disc pl-6 my-4 space-y-2">
						<li>The right to request access to your personal data.</li>
						<li>The right to request correction of your personal data.</li>
						<li>The right to request erasure of your personal data.</li>
						<li>The right to object to processing of your personal data.</li>
						<li>The right to request restriction of processing your personal data.</li>
						<li>The right to request transfer of your personal data.</li>
						<li>The right to withdraw consent.</li>
					</ul>
					<p className="mt-4">
						Please note that these rights are not absolute, and we may be entitled to refuse
						requests where exceptions apply. If you wish to exercise any of the rights set out
						above, please contact us. We may need to request specific information from you to help
						us confirm your identity and ensure your right to access your personal data.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">7. Third-Party Services</h2>
					<p>
						Our service may contain links to other websites that are not operated by us. If you
						click on a third-party link, you will be directed to that third party's site. We
						strongly advise you to review the Privacy Policy of every site you visit. We have no
						control over and assume no responsibility for the content, privacy policies, or
						practices of any third-party sites or services.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">8. Contact Us</h2>
					<p>
						If you have any questions about this privacy policy or our privacy practices, please
						contact us at:
					</p>
					<p className="mt-2">
						<strong>Email:</strong> rohan@surfsense.com
					</p>
				</section>
			</div>
		</div>
	);
}
