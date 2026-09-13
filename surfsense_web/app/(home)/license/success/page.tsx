import type { Metadata } from "next";
import { Suspense } from "react";
import { LicenseDownload } from "./license-download";

export const metadata: Metadata = {
	title: "Thanks for buying SurfSense",
	robots: { index: false, follow: false },
};

export default function LicenseSuccessPage() {
	return (
		<div className="container mx-auto max-w-2xl px-4 pt-28 pb-16">
			<div className="flex flex-col gap-8">
				<div className="flex flex-col gap-4">
					<h1 className="text-4xl font-bold text-balance">Thanks &mdash; you are all set</h1>
					<p className="text-lg text-pretty text-muted-foreground">
						Your license file is below. Save it now: it is the thing that unlocks plugins and
						priority support, and we have also emailed you a copy.
					</p>
				</div>

				<Suspense fallback={null}>
					<LicenseDownload />
				</Suspense>

				<div className="flex flex-col gap-4 border-t pt-8 text-sm text-muted-foreground">
					<div className="flex flex-col gap-2">
						<h2 className="font-medium text-foreground">Install it</h2>
						<ol className="flex list-decimal flex-col gap-1 pl-5">
							<li>
								Save <code className="font-mono">surfsense.lic</code> somewhere you can find it.
							</li>
							<li>Open SurfSense and go to Settings &rarr; License.</li>
							<li>Drop the file in, or paste its contents.</li>
						</ol>
						<p>
							SurfSense never contacts a license server. The file is checked on your own machine, so
							it works offline and on every computer you install SurfSense on.
						</p>
					</div>
					<div className="flex flex-col gap-2">
						<h2 className="font-medium text-foreground">Lose the file later?</h2>
						<p>
							Get it emailed again at{" "}
							<a className="underline" href="/license">
								surfsense.com/license
							</a>
							, using the address you bought with.
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
