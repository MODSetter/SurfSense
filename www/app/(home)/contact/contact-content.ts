import { EMAIL, REPO_URL } from "@/components/site/site-content";

/**
 * Contact page copy.
 *
 * Kept apart from the markup for the same reason the homepage and pricing copy
 * are: the sections are layout, this is the thing that actually gets edited.
 */

export const DISCORD_URL = "https://discord.gg/ejRNvftDp9";
export const ISSUES_URL = `${REPO_URL}/issues`;
export const DISCUSSIONS_URL = `${REPO_URL}/discussions`;
export { EMAIL };

export type Channel = {
	/** The short label above the heading: what kind of message this is for. */
	eyebrow: string;
	title: string;
	body: string;
	action: { label: string; href: string; external?: boolean };
};

/**
 * Three ways in. SurfSense is free and kept up by its creator as a side project, so there
 * are no licences, sales calls or procurement to route; each cell says plainly what it is
 * for rather than leaving the visitor to guess which address to use.
 */
export const CHANNELS: Channel[] = [
	{
		eyebrow: "Anything else",
		title: "Send an email",
		body: "Privacy requests, security reports, press, or a question that does not fit anywhere else. Every message is read, though a reply can take a few days.",
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
