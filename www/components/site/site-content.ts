/**
 * Shared site chrome: the addresses and link types the navigation, the footer and
 * the pages share. The nav and footer themselves, before and after the Business
 * launch switch, are in `features/site-navigation/site-navigation.ts`.
 *
 * The nav and footer belong to the whole site, not the home page: they are
 * rendered once by `app/(home)/layout.tsx` and kept mounted across navigations.
 */

import type { Icon } from "@/components/ui/icons";

export const REPO_URL = "https://github.com/MODSetter/SurfSense";
export const DISCORD_URL = "https://discord.gg/ejRNvftDp9";
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

/**
 * The audience and job pages, from `plans/community-local/seo/09-audience-pages.md`. Each
 * slug is its page's primary keyword. They exist only once Business is on sale.
 */
export const LAWYERS_URL = "/ai-for-lawyers";
export const ACCOUNTANTS_URL = "/ai-for-accountants";
export const CONTRACT_REDLINE_URL = "/jobs/contract-redline";
export const SECURITY_QUESTIONNAIRE_URL = "/jobs/security-questionnaire";

/**
 * The free audiences and the Studio jobs they search for, from the same plan's round two.
 * They name no paid job, so they exist with or without the Business switch.
 */
export const STUDENTS_URL = "/ai-for-students";
export const TEACHERS_URL = "/ai-for-teachers";
export const STUDY_GUIDE_URL = "/features/study-guide-maker";
export const FLASHCARDS_URL = "/features/flashcard-generator";
export const QUIZ_URL = "/features/quiz-generator";
export const PODCAST_URL = "/features/podcast-generator";

/** Every page round two adds, for the sitemap. */
export const STUDY_PAGES = [
	STUDENTS_URL,
	TEACHERS_URL,
	STUDY_GUIDE_URL,
	FLASHCARDS_URL,
	QUIZ_URL,
	PODCAST_URL,
];

export type FooterLink = { title: string; href: string; external?: boolean };
