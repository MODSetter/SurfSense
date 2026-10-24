/**
 * Shared site chrome: the links that appear in the navigation and footer on
 * every page.
 *
 * The nav and footer belong to the whole site, not the home page: they are
 * rendered once by `app/(home)/layout.tsx` and kept mounted across navigations.
 */

import {
	BookOpen01Icon,
	HistoryIcon,
	type Icon,
	Mail01Icon,
	Megaphone01Icon,
} from "@/components/ui/icons";

export const REPO_URL = "https://github.com/MODSetter/SurfSense";
export const DOWNLOADS_URL = "/downloads";
/** The inbox the contact and pricing pages give out. */
export const EMAIL = "rohan@surfsense.com";

/**
 * The cross-cutting professional page. The slug is the page's primary keyword
 * (`private ai for business`) rather than the job it does, because the literal
 * phrasings for that job are unsearched — `pdf to presentation` is 110 a month
 * and `document to presentation` is 10
 * (`plans/community-local/seo/02-page-briefs.md`).
 */
export const BUSINESS_URL = "/private-ai-for-business";

export type SiteLink = { name: string; href: string; external?: boolean };
export type SiteMenuItem = SiteLink & { description: string; icon: Icon };

export const NAV_LINKS: SiteLink[] = [
	{ name: "For business", href: BUSINESS_URL },
	{ name: "Plugins", href: "/plugins" },
	{ name: "Docs", href: "/docs" },
	{ name: "Pricing", href: "/pricing" },
];

export const NAV_RESOURCES: SiteMenuItem[] = [
	{
		name: "Blog",
		href: "/blog",
		description: "Guides, comparisons and deep dives",
		icon: BookOpen01Icon,
	},
	{
		name: "Announcements",
		href: "/announcements",
		description: "Product news and updates",
		icon: Megaphone01Icon,
	},
	{
		name: "Changelog",
		href: "/changelog",
		description: "What's new in SurfSense",
		icon: HistoryIcon,
	},
	{
		name: "Contact us",
		href: "/contact",
		description: "Questions, bugs and feedback",
		icon: Mail01Icon,
	},
];

export type FooterLink = { title: string; href: string; external?: boolean };

export const FOOTER_COLUMNS: { heading: string; links: FooterLink[] }[] = [
	{
		heading: "Product",
		links: [
			{ title: "Download", href: DOWNLOADS_URL },
			{ title: "For business", href: BUSINESS_URL },
			{ title: "Plugins", href: "/plugins" },
			{ title: "Pricing", href: "/pricing" },
			{ title: "Docs", href: "/docs" },
		],
	},
	{
		heading: "Resources",
		links: [
			{ title: "Blog", href: "/blog" },
			{ title: "Announcements", href: "/announcements" },
			{ title: "Changelog", href: "/changelog" },
			{ title: "Contact us", href: "/contact" },
		],
	},
	{
		heading: "Company",
		links: [
			{ title: "Privacy Policy", href: "/privacy" },
			{ title: "Terms of Service", href: "/terms" },
		],
	},
];
