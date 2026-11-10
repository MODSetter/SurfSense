import {
	ACCOUNTANTS_URL,
	BUSINESS_URL,
	CONTRACT_REDLINE_URL,
	DOWNLOADS_URL,
	FLASHCARDS_URL,
	type FooterLink,
	LAWYERS_URL,
	PODCAST_URL,
	QUIZ_URL,
	SECURITY_QUESTIONNAIRE_URL,
	type SiteLink,
	type SiteMenuItem,
	STUDENTS_URL,
	STUDY_GUIDE_URL,
	TEACHERS_URL,
} from "@/components/site/site-content";
import {
	BookOpen01Icon,
	Briefcase01Icon,
	Calculator01Icon,
	Cards01Icon,
	HistoryIcon,
	JusticeScale01Icon,
	LegalDocument01Icon,
	Mail01Icon,
	Megaphone01Icon,
	Mortarboard01Icon,
	Notebook01Icon,
	Plug01Icon,
	PodcastIcon,
	Quiz02Icon,
	SecurityCheckIcon,
	TeacherIcon,
} from "@/components/ui/icons";

/**
 * The site's navigation and footer, before and after the Business launch switch
 * (`NEXT_PUBLIC_BUSINESS_LAUNCHED`). Functions of the switch rather than constants, so
 * `site-navigation.test.ts` can check both sites; `SiteNav` and `SiteFooter` pass
 * `BUSINESS_LAUNCHED`.
 *
 * The bar opens on a "For" menu, which took the place of the "For business" link on
 * 10 Nov 2026 at the maintainer's ask: who SurfSense is for, then the jobs, then the study
 * tools (`plans/community-local/seo/09-audience-pages.md`, "The nav"). Before the switch it
 * holds only the pages that exist then. Switched on, Plugins leaves the bar for Resources:
 * once the scrapers retire, its page holds the three built-in sources and third-party
 * plugins.
 */

/** A run of a menu's links under one heading; a menu of one group needs no heading. */
export type NavGroup = { heading?: string; items: SiteMenuItem[] };
export type NavMenu = { name: string; groups: NavGroup[] };
export type NavEntry = SiteLink | NavMenu;
export type FooterColumn = { heading: string; links: FooterLink[] };

export function isNavMenu(entry: NavEntry): entry is NavMenu {
	return "groups" in entry;
}

/** Every link in a menu, group after group. */
export function menuItems(menu: NavMenu): SiteMenuItem[] {
	return menu.groups.flatMap((group) => group.items);
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

const LAWYERS: SiteMenuItem = {
	name: "Lawyers",
	href: LAWYERS_URL,
	description: "Client files kept on your own computer",
	icon: JusticeScale01Icon,
};
const ACCOUNTANTS: SiteMenuItem = {
	name: "Accountants",
	href: ACCOUNTANTS_URL,
	description: "Client financial files, kept on your machine",
	icon: Calculator01Icon,
};
const STUDENTS: SiteMenuItem = {
	name: "Students",
	href: STUDENTS_URL,
	description: "Flashcards, quizzes and study guides, free",
	icon: Mortarboard01Icon,
};
const TEACHERS: SiteMenuItem = {
	name: "Teachers",
	href: TEACHERS_URL,
	description: "Quizzes, worksheets and lesson plans, free",
	icon: TeacherIcon,
};
const BUSINESS: SiteMenuItem = {
	name: "Business",
	href: BUSINESS_URL,
	description: "Decks and reports from confidential files",
	icon: Briefcase01Icon,
};

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

const STUDY_TOOLS: SiteMenuItem[] = [
	{
		name: "Study guide maker",
		href: STUDY_GUIDE_URL,
		description: "A summary, flashcards and a quiz",
		icon: Notebook01Icon,
	},
	{
		name: "Flashcard generator",
		href: FLASHCARDS_URL,
		description: "Cards from your PDFs and notes",
		icon: Cards01Icon,
	},
	{
		name: "Quiz generator",
		href: QUIZ_URL,
		description: "Practice quizzes from your material",
		icon: Quiz02Icon,
	},
	{
		name: "Podcast generator",
		href: PODCAST_URL,
		description: "Audio from your documents, made offline",
		icon: PodcastIcon,
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

/** Who SurfSense is for, the jobs and the study tools, holding only the pages that exist. */
function forMenu(launched: boolean): NavMenu {
	if (!launched) {
		return {
			name: "For",
			groups: [
				{ heading: "Who it's for", items: [STUDENTS, TEACHERS, BUSINESS] },
				{ heading: "Study tools", items: STUDY_TOOLS },
			],
		};
	}
	return {
		name: "For",
		groups: [
			{ heading: "Who it's for", items: [LAWYERS, ACCOUNTANTS, STUDENTS, TEACHERS, BUSINESS] },
			{ heading: "Jobs", items: JOBS },
			{ heading: "Study tools", items: STUDY_TOOLS },
		],
	};
}

export function siteNavigation(launched: boolean): NavEntry[] {
	if (!launched) {
		return [
			forMenu(false),
			{ name: "Plugins", href: PLUGINS.href },
			{ name: "Docs", href: "/docs" },
			{ name: "Pricing", href: "/pricing" },
			{ name: "Resources", groups: [{ items: [BLOG, ANNOUNCEMENTS, CHANGELOG, CONTACT] }] },
		];
	}
	return [
		forMenu(true),
		{ name: "Docs", href: "/docs" },
		{ name: "Pricing", href: "/pricing" },
		{
			name: "Resources",
			groups: [{ items: [BLOG, ANNOUNCEMENTS, CHANGELOG, PLUGINS, CONTACT] }],
		},
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
				{ title: "Contract redline", href: CONTRACT_REDLINE_URL },
				{ title: "Security questionnaire", href: SECURITY_QUESTIONNAIRE_URL },
				{ title: "Docs", href: "/docs" },
				{ title: "Plugins", href: PLUGINS.href },
			],
		},
		{
			heading: "Who it's for",
			links: [
				{ title: "AI for lawyers", href: LAWYERS_URL },
				{ title: "AI for accountants", href: ACCOUNTANTS_URL },
				{ title: "AI for students", href: STUDENTS_URL },
				{ title: "AI for teachers", href: TEACHERS_URL },
				{ title: "Private AI for business", href: BUSINESS_URL },
			],
		},
		RESOURCES_COLUMN,
		COMPANY_COLUMN,
	];
}
