import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "Terms of Service | SurfSense",
	description: "Terms of Service for SurfSense application",
};

export default function TermsOfService() {
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="text-4xl font-bold mb-8">Terms of Service</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">Last updated: {new Date().toLocaleDateString()}</p>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">1. Introduction</h2>
					<p>
						Welcome to SurfSense. These Terms of Service govern your access to and use of the
						SurfSense website and services. By accessing or using our services, you agree to be
						bound by these Terms.
					</p>
					<p className="mt-4">
						Please read these Terms carefully before using our Services. By using our Services, you
						agree that these Terms will govern your relationship with us. If you do not agree to
						these Terms, please refrain from using our Services.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">2. Using Our Services</h2>
					<p>
						You must follow any policies made available to you within the Services. You may use our
						Services only as permitted by law. We may suspend or stop providing our Services to you
						if you do not comply with our terms or policies or if we are investigating suspected
						misconduct.
					</p>
					<p className="mt-4">
						Using our Services does not give you ownership of any intellectual property rights in
						our Services or the content you access. You may not use content from our Services unless
						you obtain permission from its owner or are otherwise permitted by law.
					</p>
					<p className="mt-4">
						We reserve the right to remove any content that we reasonably believe violates these
						Terms, infringes any intellectual property right, is abusive, illegal, or otherwise
						objectionable.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">3. Your Account</h2>
					<p>
						To use some of our services, you may need to create an account. You are responsible for
						safeguarding the password that you use to access the services and for any activities or
						actions under your password.
					</p>
					<p className="mt-4">
						You must provide accurate and complete information when creating your account. You agree
						to update your information to keep it accurate and complete. You are responsible for
						maintaining the confidentiality of your account and password, including restricting
						access to your computer and/or account.
					</p>
					<p className="mt-4">
						We reserve the right to refuse service, terminate accounts, remove or edit content, or
						cancel orders at our sole discretion.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">4. Privacy and Copyright Protection</h2>
					<p>
						Our privacy policies explain how we treat your personal data and protect your privacy
						when you use our Services. By using our Services, you agree that SurfSense can use such
						data in accordance with our privacy policies.
					</p>
					<p className="mt-4">
						We respond to notices of alleged copyright infringement and terminate accounts of repeat
						infringers according to the process set out in applicable copyright laws.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">5. License and Intellectual Property</h2>
					<p>
						SurfSense gives you a personal, worldwide, royalty-free, non-assignable and
						non-exclusive license to use the software provided to you as part of the Services. This
						license is for the sole purpose of enabling you to use and enjoy the benefit of the
						Services as provided by SurfSense, in the manner permitted by these terms.
					</p>
					<p className="mt-4">
						All content included in or made available through our Services—such as text, graphics,
						logos, button icons, images, audio clips, digital downloads, data compilations, and
						software—is the property of SurfSense or its content suppliers and is protected by
						international copyright, trademark, and other intellectual property laws.
					</p>
					<p className="mt-4">
						By submitting, posting, or displaying content on or through our Services, you grant us a
						worldwide, non-exclusive, royalty-free license to use, reproduce, modify, adapt,
						publish, translate, create derivative works from, distribute, and display such content
						in any media for the purpose of providing and improving our Services.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">6. Modifying and Terminating our Services</h2>
					<p>
						We are constantly changing and improving our Services. We may add or remove
						functionalities or features, and we may suspend or stop a Service altogether. You can
						stop using our Services at any time. SurfSense may also stop providing Services to you,
						or add or create new limits on our Services at any time.
					</p>
					<p className="mt-4">
						We believe that you own your data and preserving your access to such data is important.
						If we discontinue a Service, where reasonably possible, we will give you reasonable
						advance notice and a chance to get information out of that Service.
					</p>
					<p className="mt-4">
						We reserve the right to modify these Terms at any time. If we make material changes to
						these Terms, we will notify you by email or by posting a notice on our website before
						the changes become effective. Your continued use of our Services after the effective
						date of such changes constitutes your acceptance of the modified Terms.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">7. Warranties and Disclaimers</h2>
					<p>
						We provide our Services using a commercially reasonable level of skill and care and we
						hope that you will enjoy using them. But there are certain things that we don't promise
						about our Services.
					</p>
					<p className="mt-4 uppercase font-bold">
						OTHER THAN AS EXPRESSLY SET OUT IN THESE TERMS OR ADDITIONAL TERMS, NEITHER SURFSENSE
						NOR ITS SUPPLIERS OR DISTRIBUTORS MAKE ANY SPECIFIC PROMISES ABOUT THE SERVICES. FOR
						EXAMPLE, WE DON'T MAKE ANY COMMITMENTS ABOUT THE CONTENT WITHIN THE SERVICES, THE
						SPECIFIC FUNCTIONS OF THE SERVICES, OR THEIR RELIABILITY, AVAILABILITY, OR ABILITY TO
						MEET YOUR NEEDS. WE PROVIDE THE SERVICES "AS IS".
					</p>
					<p className="mt-4 uppercase font-bold">
						SOME JURISDICTIONS PROVIDE FOR CERTAIN WARRANTIES, LIKE THE IMPLIED WARRANTY OF
						MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. TO THE EXTENT
						PERMITTED BY LAW, WE EXCLUDE ALL WARRANTIES.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">8. Liability for our Services</h2>
					<p className="uppercase font-bold">
						WHEN PERMITTED BY LAW, SURFSENSE, AND SURFSENSE'S SUPPLIERS AND DISTRIBUTORS, WILL NOT
						BE RESPONSIBLE FOR LOST PROFITS, REVENUES, OR DATA, FINANCIAL LOSSES OR INDIRECT,
						SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES.
					</p>
					<p className="mt-4 uppercase font-bold">
						TO THE EXTENT PERMITTED BY LAW, THE TOTAL LIABILITY OF SURFSENSE, AND ITS SUPPLIERS AND
						DISTRIBUTORS, FOR ANY CLAIMS UNDER THESE TERMS, INCLUDING FOR ANY IMPLIED WARRANTIES, IS
						LIMITED TO THE AMOUNT YOU PAID US TO USE THE SERVICES (OR, IF WE CHOOSE, TO SUPPLYING
						YOU THE SERVICES AGAIN).
					</p>
					<p className="mt-4 uppercase font-bold">
						IN ALL CASES, SURFSENSE, AND ITS SUPPLIERS AND DISTRIBUTORS, WILL NOT BE LIABLE FOR ANY
						LOSS OR DAMAGE THAT IS NOT REASONABLY FORESEEABLE.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">9. Indemnification</h2>
					<p>
						You agree to defend, indemnify, and hold harmless SurfSense, its affiliates, and their
						respective officers, directors, employees, and agents from and against any claims,
						liabilities, damages, judgments, awards, losses, costs, expenses, or fees (including
						reasonable attorneys' fees) arising out of or relating to your violation of these Terms
						or your use of the Services, including, but not limited to, any use of the Services'
						content, services, and products other than as expressly authorized in these Terms.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">10. Dispute Resolution</h2>
					<p>
						Any dispute arising out of or relating to these Terms, including the validity,
						interpretation, breach, or termination thereof, shall be resolved by arbitration in
						accordance with the rules of the arbitration authority in the jurisdiction where
						SurfSense operates. The arbitration shall be conducted by one arbitrator, in the English
						language, and the decision of the arbitrator shall be final and binding on the parties.
					</p>
					<p className="mt-4">
						You agree that any dispute resolution proceedings will be conducted only on an
						individual basis and not in a class, consolidated, or representative action. If for any
						reason a claim proceeds in court rather than in arbitration, you waive any right to a
						jury trial.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">11. About these Terms</h2>
					<p>
						We may modify these terms or any additional terms that apply to a Service to, for
						example, reflect changes to the law or changes to our Services. You should look at the
						terms regularly. If you do not agree to the modified terms for a Service, you should
						discontinue your use of that Service.
					</p>
					<p className="mt-4">
						If there is a conflict between these terms and the additional terms, the additional
						terms will control for that conflict. These terms control the relationship between
						SurfSense and you. They do not create any third-party beneficiary rights.
					</p>
					<p className="mt-4">
						If you do not comply with these terms, and we don't take action right away, this doesn't
						mean that we are giving up any rights that we may have (such as taking action in the
						future). If it turns out that a particular term is not enforceable, this will not affect
						any other terms.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">12. Contact Us</h2>
					<p>If you have any questions about these Terms, please contact us at:</p>
					<p className="mt-2">
						<strong>Email:</strong> rohan@surfsense.com
					</p>
				</section>
			</div>
		</div>
	);
}
