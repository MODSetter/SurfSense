import type { Metadata } from "next";
import {
	ContactBugReports,
	ContactChannels,
	ContactEnterprise,
	ContactHero,
} from "@/components/contact/contact-sections";

/**
 * Contact page.
 *
 * Rendered in the site design: the palette, ruled column, navigation and footer
 * all come from `app/(home)/layout.tsx`, and every style on this page resolves
 * from `app/(home)/home.css`. It is listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, which is what puts it inside the ruled
 * column rather than on the older gradient ground.
 *
 * A server component with no client JavaScript. Every element on the page is a
 * link.
 */

const canonicalUrl = "https://www.surfsense.com/contact";

const metaTitle = "Contact SurfSense";
const metaDescription =
	"Book a call, send an email, file a GitHub issue or ask in Discord. Team licences, enterprise procurement and bug reports all go to a person, not a form.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	alternates: {
		canonical: canonicalUrl,
	},
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Contact SurfSense" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

export default function ContactPage() {
	return (
		<>
			<ContactHero />
			<ContactChannels />
			<ContactBugReports />
			<ContactEnterprise />
		</>
	);
}
