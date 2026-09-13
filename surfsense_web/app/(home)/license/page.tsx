import type { Metadata } from "next";
import { LicenseForms } from "./license-forms";

export const metadata: Metadata = {
	title: "Your license | SurfSense",
	description: "Get your SurfSense license file sent to your email again, or start a 14-day trial.",
	alternates: { canonical: "https://www.surfsense.com/license" },
};

export default function LicensePage() {
	return (
		<div className="container mx-auto max-w-2xl px-4 pt-28 pb-16">
			<div className="flex flex-col gap-8">
				<div className="flex flex-col gap-4">
					<h1 className="text-4xl font-bold text-balance">Your SurfSense license</h1>
					<p className="text-lg text-pretty text-muted-foreground">
						There is no account to sign in to. Your license lives in a file, and your email address
						is how we find it.
					</p>
				</div>

				<LicenseForms />

				<div className="flex flex-col gap-4 border-t pt-8 text-sm text-muted-foreground">
					<div className="flex flex-col gap-2">
						<h2 className="font-medium text-foreground">Where the file goes</h2>
						<p>
							Save the attached <code className="font-mono">surfsense.lic</code>, open SurfSense, go
							to Settings &rarr; License, and drop it in. Your license never expires the app: when
							it runs out, SurfSense keeps working and your data stays put.
						</p>
					</div>
					<div className="flex flex-col gap-2">
						<h2 className="font-medium text-foreground">Bought for a team?</h2>
						<p>
							A team license is one file for everyone. It is sent only to the address that bought
							it, so ask whoever made the purchase to forward it to you.
						</p>
					</div>
					<div className="flex flex-col gap-2">
						<h2 className="font-medium text-foreground">Cannot get into that inbox?</h2>
						<p>
							If you mistyped your email when buying, or no longer have access to it, we cannot send
							the file anywhere else automatically &mdash; otherwise anyone could type your address
							and receive your license. Email{" "}
							<a
								className="underline"
								href="mailto:support@surfsense.com?subject=License%20recovery"
							>
								support@surfsense.com
							</a>{" "}
							with your payment details (the charge on your card statement, or the last 4 digits,
							amount and date) and we will verify the purchase and fix it.
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
