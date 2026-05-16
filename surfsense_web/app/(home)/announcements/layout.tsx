import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "What's New | SurfSense",
	description: "Latest product updates, feature releases, and news from SurfSense.",
	alternates: {
		canonical: "https://www.surfsense.com/announcements",
	},
	openGraph: {
		title: "What's New | SurfSense",
		description: "Latest product updates, feature releases, and news from SurfSense.",
		url: "https://www.surfsense.com/announcements",
		type: "website",
	},
	twitter: {
		card: "summary_large_image",
		title: "What's New | SurfSense",
		description: "Latest product updates, feature releases, and news from SurfSense.",
	},
};

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
