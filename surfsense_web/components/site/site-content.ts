/**
 * Shared site chrome: the links that appear in the navigation and footer on
 * every page.
 *
 * These live outside `components/homepage/` because the nav and footer are no
 * longer homepage furniture — they are the site's furniture, rendered once by
 * `app/(home)/layout.tsx` and kept mounted across navigations.
 */

export const REPO_URL = "https://github.com/MODSetter/SurfSense";
export const DOWNLOADS_URL = "/downloads";

export type SiteLink = { name: string; href: string; external?: boolean };
export type SiteMenuItem = SiteLink & { description: string };

export const NAV_LINKS: SiteLink[] = [
	{ name: "Plugins", href: "/plugins" },
	{ name: "Docs", href: "/docs" },
	{ name: "Pricing", href: "/pricing" },
];

export const NAV_RESOURCES: SiteMenuItem[] = [
	{ name: "Blog", href: "/blog", description: "Guides, comparisons and deep dives" },
	{ name: "Announcements", href: "/announcements", description: "Product news and updates" },
	{ name: "Changelog", href: "/changelog", description: "What's new in SurfSense" },
	{ name: "Contact us", href: "/contact", description: "Questions, bugs and feedback" },
];

export type FooterLink = { title: string; href: string; external?: boolean };

export const FOOTER_COLUMNS: { heading: string; links: FooterLink[] }[] = [
	{
		heading: "Product",
		links: [
			{ title: "Download", href: DOWNLOADS_URL },
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
