import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "SurfSense is moving | SurfSense",
	robots: { index: false, follow: false },
};

export default function SunsetPage() {
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="text-4xl font-bold mb-8">SurfSense is moving to a local app</h1>
			<p className="text-lg">Details, export and download steps will appear here soon.</p>
		</div>
	);
}
