import type { Metadata } from "next";
import { SunsetExport } from "./sunset-export";

/**
 * Rendered in the site design: the palette, ruled column, navigation and
 * footer all come from `app/(home)/layout.tsx`, and every style resolves from
 * `app/(home)/home.css`. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 */

export const metadata: Metadata = {
	title: "SurfSense is moving | SurfSense",
	robots: { index: false, follow: false },
};

export default function SunsetPage() {
	return (
		<section className="ss-home-hero ss-home-pad">
			<div className="mx-auto max-w-2xl text-center">
				<h1 className="ss-home-display">SurfSense is moving to a local app</h1>
				<p className="ss-home-lede mx-auto mt-6 max-w-xl">
					The hosted app is going away. A free local app will replace it. After launch, this site
					stays up for 30 days so you can export, then hosted data is deleted. The deletion date
					will appear here once launch day is set.
				</p>
				<SunsetExport />
			</div>
		</section>
	);
}
