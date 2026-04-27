import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "Announcements | SurfSense",
	description:
		"Latest announcements, product news, and updates from the SurfSense team.",
	alternates: {
		canonical: "https://surfsense.com/announcements",
	},
};

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
	return children;
}
