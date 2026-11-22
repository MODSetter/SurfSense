import { REPO_URL } from "@/components/site/site-content";

/**
 * `/pricing`'s copy. SurfSense has been free since SurfSense Inc. wound down on 27 November
 * 2026: no licences, trials, checkout or Business plan, and every job is part of the free app.
 *
 * The URL stays because installed apps, old emails and search results link to it, so the
 * page answers "what does it cost?" for all of them. `/pricing/business` and
 * `/pricing/individual` redirect here with temporary redirects
 * (`features/business-launch/launch-redirects.mts`).
 */

export const SELF_BUILD_URL = REPO_URL;

/**
 * Answers are written as quotable definitions: one plain paragraph an AI Overview or a People
 * Also Ask box can lift verbatim.
 */
export type PricingQuestion = { question: string; answer: string };

export const PRICING_META_TITLE = "SurfSense Pricing: Free and Open Source";
export const PRICING_META_DESCRIPTION =
	"SurfSense is free: the app, every update and every job, with no licence, account, trial or usage cap. Open source under Apache-2.0.";

/** What the free app includes, one line each. */
export const FREE_INCLUDES: string[] = [
	"The full app on Windows, macOS and Linux, with every update",
	"Runs offline; your sources, chats and index stay on your disk",
	"Bring your own model keys, or run a local model for nothing",
	"Web pages, YouTube videos and web search (with your own SearXNG server) as sources",
	"Studio: flashcards, quizzes, mind maps, slides, podcasts, and Word, PDF and spreadsheet files",
	"The jobs: the security questionnaire and the contract redline",
	"Third-party plugins and any MCP server you add",
	"Open source under Apache-2.0, so you can build it yourself",
];

const FAQ_IS_IT_FREE: PricingQuestion = {
	question: "Is SurfSense free?",
	answer:
		"Yes. The app, every update and every feature, the security questionnaire and contract redline jobs included, are free, with no licence, no account, no trial and no usage cap. You download it, install it and use it, for personal or commercial work.",
};

const FAQ_WHY_FREE: PricingQuestion = {
	question: "Why is SurfSense free now?",
	answer:
		"SurfSense Inc., the company that sold SurfSense licences, wound down on 27 November 2026. SurfSense carries on as a free, open-source project, maintained by its creator, Rohan Verma, as a side project for the time being. From version 2.4.0 the app needs no licence for anything.",
};

const FAQ_BOUGHT_A_LICENCE: PricingQuestion = {
	question: "I bought a licence. What happens now?",
	answer:
		"Nothing more is charged: every renewal has been cancelled. Update to SurfSense 2.4.0 or later and every feature is unlocked with no licence file, so there is nothing to import or renew. Your files and chats stay on your computer and are not affected.",
};

const FAQ_STUDENTS_AND_TEACHERS: PricingQuestion = {
	question: "Is SurfSense free for students and teachers?",
	answer:
		"Yes, like it is for everyone: chat across your sources with a citation for every point, and Studio's flashcards, quizzes, mind maps, slides and podcasts. There is no licence or education plan to apply for.",
};

const FAQ_MODEL_COSTS: PricingQuestion = {
	question: "Do I pay for the AI model?",
	answer:
		"Only if you choose a hosted one. SurfSense runs a model on your own computer for nothing, or uses your own key for a provider such as OpenAI, Anthropic or OpenRouter, which that provider bills you for directly. SurfSense takes no cut and sees none of it.",
};

const FAQ_OPEN_SOURCE: PricingQuestion = {
	question: "Is SurfSense open source?",
	answer:
		"Yes. The whole app, including the code that used to be under the Business Source License, is under the Apache-2.0 licence on GitHub. You can read it, build it yourself and change it.",
};

const FAQ_SUPPORT: PricingQuestion = {
	question: "Is there paid support or an enterprise plan?",
	answer:
		"No. There are no paid plans of any kind. Bugs and feature requests go to GitHub issues, and setup questions to Discord, where they are answered as time allows.",
};

const FAQ_NOTEBOOKLM_LOCALLY: PricingQuestion = {
	question: "Can I run NotebookLM locally?",
	answer:
		"No. NotebookLM is a Google cloud service: it requires a Google account, uploads your sources to Google's servers, and cannot be installed on your own machine. Running the same workflow locally means using an alternative built for it, such as SurfSense, which keeps sources and answers on your computer.",
};

export const PRICING_FAQ: PricingQuestion[] = [
	FAQ_IS_IT_FREE,
	FAQ_WHY_FREE,
	FAQ_BOUGHT_A_LICENCE,
	FAQ_STUDENTS_AND_TEACHERS,
	FAQ_MODEL_COSTS,
	FAQ_OPEN_SOURCE,
	FAQ_SUPPORT,
	FAQ_NOTEBOOKLM_LOCALLY,
];

/** `SoftwareApplication` with its one offer, free. */
export const PRICING_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "SoftwareApplication",
	name: "SurfSense",
	applicationCategory: "BusinessApplication",
	operatingSystem: "Windows, macOS, Linux",
	description:
		"A private, open-source research notebook that runs on your own machine. Free, with every feature and every update, under Apache-2.0.",
	url: "https://www.surfsense.com/pricing",
	offers: {
		"@type": "Offer",
		name: "Free",
		price: 0,
		priceCurrency: "USD",
		description:
			"The full app and every update on Windows, macOS and Linux, jobs included. No licence, no account, runs offline, bring your own model keys.",
	},
};
