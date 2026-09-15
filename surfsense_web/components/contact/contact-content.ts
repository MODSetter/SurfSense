import { REPO_URL } from "@/components/site/site-content";

/**
 * Contact page copy.
 *
 * Kept apart from the markup for the same reason the homepage and pricing copy
 * are: the sections are layout, this is the thing that actually gets edited.
 */

export const CALL_URL = "https://cal.com/mod-rohan";
export const EMAIL = "rohan@surfsense.com";
export const DISCORD_URL = "https://discord.gg/ejRNvftDp9";
export const ISSUES_URL = `${REPO_URL}/issues`;
export const DISCUSSIONS_URL = `${REPO_URL}/discussions`;

export type Channel = {
	/** The short label above the heading: what kind of message this is for. */
	eyebrow: string;
	title: string;
	body: string;
	action: { label: string; href: string; external?: boolean };
};

/**
 * Four ways in, ordered by how much of our time they ask for. A bug report
 * routed to a sales call helps nobody, so each cell says plainly what it is
 * for rather than leaving the visitor to guess which address to use.
 */
export const CHANNELS: Channel[] = [
	{
		eyebrow: "Licences and rollouts",
		title: "Book a call",
		body: "Thirty minutes with the person who builds it. Best for team licences, procurement questions and deciding whether SurfSense fits how your team already works.",
		action: { label: "Find a time", href: CALL_URL, external: true },
	},
	{
		eyebrow: "Anything else",
		title: "Send an email",
		body: "Licence keys, invoices, partnerships, press, or a question that does not fit anywhere else. We read every message and usually reply within one business day.",
		action: { label: EMAIL, href: `mailto:${EMAIL}` },
	},
	{
		eyebrow: "Bugs and feature requests",
		title: "Open a GitHub issue",
		body: "Something broken, or something missing? File it on the repository so it is tracked in public, next to the code and the release it ships in.",
		action: { label: "Open an issue", href: ISSUES_URL, external: true },
	},
	{
		eyebrow: "Help and ideas",
		title: "Ask the community",
		body: "Setup questions, model choices and workflow advice get answered fastest in Discord, where other people running SurfSense locally can weigh in too.",
		action: { label: "Join the Discord", href: DISCORD_URL, external: true },
	},
];

/**
 * The details that turn a short report into one we can act on without a
 * round trip. Deliberately short: a long checklist stops people writing at all.
 */
export const BUG_REPORT_CHECKLIST = [
	{
		title: "Your platform",
		body: "Operating system, its version, and the SurfSense version from Settings → About.",
	},
	{
		title: "What you expected",
		body: "The steps you took and what should have happened at the end of them.",
	},
	{
		title: "What happened instead",
		body: "The error text verbatim, or a screenshot if the failure is visual.",
	},
	{
		title: "Your model setup",
		body: "Which provider and model the notebook was pointed at, if the problem involves answers.",
	},
];
