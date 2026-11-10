import {
	ACCOUNTANTS_URL,
	BUSINESS_URL,
	CONTRACT_REDLINE_URL,
	DOWNLOADS_URL,
	type FooterLink,
	LAWYERS_URL,
	SECURITY_QUESTIONNAIRE_URL,
	type SiteLink,
	type SiteMenuItem,
} from "@/components/site/site-content";
import {
	BookOpen01Icon,
	Briefcase01Icon,
	Calculator01Icon,
	HistoryIcon,
	JusticeScale01Icon,
	LegalDocument01Icon,
	Mail01Icon,
	Megaphone01Icon,
	Plug01Icon,
	SecurityCheckIcon,
} from "@/components/ui/icons";

/**
 * The site's navigation and footer, before and after the Business launch switch
 * (`NEXT_PUBLIC_BUSINESS_LAUNCHED`). Functions of the switch rather than constants, so
 * `site-navigation.test.ts` can check both sites; `SiteNav` and `SiteFooter` pass
 * `BUSINESS_LAUNCHED`.
 *
 * Switched on, the nav leads with who SurfSense is for and the paid jobs
 * (`plans/community-local/seo/09-audience-pages.md`, "The nav"). Plugins leaves the bar for
 * Resources: once the scrapers retire, its page holds the three built-in sources and
 * third-party plugins.
 */

export type NavMenu = { name: string; items: SiteMenuItem[] };
export type NavEntry = SiteLink | NavMenu;
export type FooterColumn = { heading: string; links: FooterLink[] };

export function isNavMenu(entry: NavEntry): entry is NavMenu {
	return "items" in entry;
}

/**
 * The pages that exist only once Business is on sale. Each is a 404 before the switch, as
 * `/pricing/business` is, because each names a paid job; from the switch on, the sitemap
 * lists them.
 */
export const BUSINESS_PAGES = [
	LAWYERS_URL,
	ACCOUNTANTS_URL,
	CONTRACT_REDLINE_URL,
	SECURITY_QUESTIONNAIRE_URL,
];

/** Who it's for. An audience joins the menu once its page is live. */
const AUDIENCES: SiteMenuItem[] = [
	{
		name: "Lawyers",
		href: LAWYERS_URL,
		description: "Client files that never leave your computer",
		icon: JusticeScale01Icon,
	},
	{
		name: "Accountants",
		href: ACCOUNTANTS_URL,
		description: "Client financial files, kept on your machine",
		icon: Calculator01Icon,
	},
	{
		name: "Other professional work",
		href: BUSINESS_URL,
		description: "Decks and reports from confidential files",
		icon: Briefcase01Icon,
	},
];

const JOBS: SiteMenuItem[] = [
	{
		name: "Contract redline",
		href: CONTRACT_REDLINE_URL,
		description: "Review a contract against your playbook",
		icon: LegalDocument01Icon,
	},
	{
		name: "Security questionnaire",
		href: SECURITY_QUESTIONNAIRE_URL,
		description: "Answer one from your own policies",
		icon: SecurityCheckIcon,
	},
];

const BLOG: SiteMenuItem = {
	name: "Blog",
	href: "/blog",
	description: "Guides, comparisons and deep dives",
	icon: BookOpen01Icon,
};
const ANNOUNCEMENTS: SiteMenuItem = {
	name: "Announcements",
	href: "/announcements",
	description: "Product news and updates",
	icon: Megaphone01Icon,
};
const CHANGELOG: SiteMenuItem = {
	name: "Changelog",
	href: "/changelog",
	description: "What's new in SurfSense",
	icon: HistoryIcon,
};
const PLUGINS: SiteMenuItem = {
	name: "Plugins",
	href: "/plugins",
	description: "Web search and YouTube built in, and more",
	icon: Plug01Icon,
};
const CONTACT: SiteMenuItem = {
	name: "Contact us",
	href: "/contact",
	description: "Questions, bugs and feedback",
	icon: Mail01Icon,
};

export function siteNavigation(launched: boolean): NavEntry[] {
	if (!launched) {
		return [
			{ name: "For business", href: BUSINESS_URL },
			{ name: "Plugins", href: PLUGINS.href },
			{ name: "Docs", href: "/docs" },
			{ name: "Pricing", href: "/pricing" },
			{ name: "Resources", items: [BLOG, ANNOUNCEMENTS, CHANGELOG, CONTACT] },
		];
	}
	return [
		{ name: "Who it's for", items: AUDIENCES },
		{ name: "Jobs", items: JOBS },
		{ name: "Docs", href: "/docs" },
		{ name: "Pricing", href: "/pricing" },
		{ name: "Resources", items: [BLOG, ANNOUNCEMENTS, CHANGELOG, PLUGINS, CONTACT] },
	];
}

const RESOURCES_COLUMN: FooterColumn = {
	heading: "Resources",
	links: [BLOG, ANNOUNCEMENTS, CHANGELOG, CONTACT].map((item) => ({
		title: item.name,
		href: item.href,
	})),
};

const COMPANY_COLUMN: FooterColumn = {
	heading: "Company",
	links: [
		{ title: "Privacy Policy", href: "/privacy" },
		{ title: "Terms of Service", href: "/terms" },
	],
};

/** Switched on, the footer's anchors carry each page's keyword rather than the menu's short name. */
export function footerColumns(launched: boolean): FooterColumn[] {
	if (!launched) {
		return [
			{
				heading: "Product",
				links: [
					{ title: "Download", href: DOWNLOADS_URL },
					{ title: "For business", href: BUSINESS_URL },
					{ title: "Plugins", href: PLUGINS.href },
					{ title: "Pricing", href: "/pricing" },
					{ title: "Docs", href: "/docs" },
				],
			},
			RESOURCES_COLUMN,
			COMPANY_COLUMN,
		];
	}
	return [
		{
			heading: "Product",
			links: [
				{ title: "Download", href: DOWNLOADS_URL },
				{ title: "Pricing", href: "/pricing" },
				{ title: "Docs", href: "/docs" },
				{ title: "Plugins", href: PLUGINS.href },
			],
		},
		{
			heading: "For firms",
			links: [
				{ title: "AI for lawyers", href: LAWYERS_URL },
				{ title: "AI for accountants", href: ACCOUNTANTS_URL },
				{ title: "Private AI for business", href: BUSINESS_URL },
				{ title: "Contract redline", href: CONTRACT_REDLINE_URL },
				{ title: "Security questionnaire", href: SECURITY_QUESTIONNAIRE_URL },
			],
		},
		RESOURCES_COLUMN,
		COMPANY_COLUMN,
	];
}
