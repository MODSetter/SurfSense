import type { Metadata } from "next";
import { SunsetExport } from "./sunset-export";

export const metadata: Metadata = {
	title: "SurfSense is moving | SurfSense",
	robots: { index: false, follow: false },
};

export default function SunsetPage() {
	return (
		<div className="container mx-auto max-w-2xl px-4 pt-28 pb-16">
			<div className="flex flex-col gap-8">
				<div className="flex flex-col gap-4">
					<h1 className="text-4xl font-bold text-balance">
						SurfSense is moving to a local app
					</h1>
					<p className="text-lg text-pretty text-muted-foreground">
						The hosted app is going away. A free local app will replace it. After launch, this
						site stays up for 30 days so you can export, then hosted data is deleted. The deletion
						date will appear here once launch day is set.
					</p>
				</div>
				<SunsetExport />
			</div>
		</div>
	);
}
