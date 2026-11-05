import {
	FAQ_NOTEBOOKLM_LOCALLY,
	FEATURE_REQUEST_LINE,
	type Plan,
	type PricingLede,
	type PricingQuestion,
} from "@/app/(home)/pricing/pricing-content";
import { DOWNLOADS_URL, EMAIL } from "@/components/site/site-content";
import {
	businessYearlyPrice,
	FIRST_PERSON_PRICE,
	FURTHER_PERSON_PRICE,
	SELF_SERVE_PEOPLE,
	yearlyPriceLabel,
} from "./business-price";

/**
 * `/pricing` once Business is on sale (`NEXT_PUBLIC_BUSINESS_LAUNCHED`), from ADR 0080, ADR 0083 and the
 * `/pricing` brief in `plans/community-local/seo/02-page-briefs.md` as revised on 1 Nov 2026.
 * When the switch goes, this replaces `pricing-content.ts`.
 *
 * Three claims follow the recommended defaults of ADR 0080's open questions, not decisions:
 * priority support and the feature build request carried over from Individual (n), every job
 * included in Business (a), and 15 people as the most a self-serve licence covers (k).
 *
 * No line says a licence works on every computer: Business counts people, not devices, and
 * device activation may come later. The market prices behind the price stay off the page.
 */

export const BUSINESS_CHECKOUT_URL = "/pricing/business";

const FIRST = yearlyPriceLabel(FIRST_PERSON_PRICE);
const FURTHER = yearlyPriceLabel(FURTHER_PERSON_PRICE);

function priceFor(people: number) {
	return yearlyPriceLabel(businessYearlyPrice(people));
}

export const BUSINESS_META_TITLE = "SurfSense Pricing: Free App, Business Licence";
export const BUSINESS_META_DESCRIPTION = `The app and its updates are free forever, with no account. A Business licence adds the job plugins, ${FIRST} a year for one person and ${FURTHER} for each more.`;

export const BUSINESS_PRICING_LEDE: PricingLede = {
	before: "The app and every update are ",
	highlight: "free, forever",
	after:
		", with no account, no trial clock and no usage cap, and reading web pages, YouTube and web search are free too. A Business licence adds the job plugins, priced per person, and a 14-day trial of the job comes with the app.",
};

export const BUSINESS_PLANS: Plan[] = [
	{
		name: "Free",
		price: "$0",
		note: "Includes a 14-day trial of the job, no card",
		summary: "The app and every update, forever. No account, no expiry.",
		features: [
			"The full app on Windows, macOS and Linux",
			"Runs offline; your sources stay on your disk",
			"Bring your own model keys, or run a local model",
			"Web pages, YouTube videos and web search as sources",
			"A 14-day trial of the security questionnaire job, by email",
			"Open source, so you can build it yourself",
		],
		action: [{ label: "Download", href: DOWNLOADS_URL }],
	},
	{
		name: "Business",
		price: FIRST,
		period: "/year",
		note: `One person is Solo. Each further person adds ${FURTHER} a year.`,
		summary: "SurfSense's job plugins for your firm, at a founding price per person.",
		features: [
			"Everything in Free",
			"The job plugins, starting with the security questionnaire",
			`Counted in people, not devices: 5 people are ${priceFor(5)} a year`,
			"Renews every year on the same licence until you cancel",
			"Cancel or change the number of people from an emailed link",
			"Priority support",
			FEATURE_REQUEST_LINE,
		],
		action: [{ label: "Buy Business", href: BUSINESS_CHECKOUT_URL, primary: true }],
		featured: true,
		badge: "Founding price",
	},
	{
		name: "Enterprise",
		price: "Custom",
		note: "Annual, invoiced",
		summary: `For more than ${SELF_SERVE_PEOPLE} people, or SurfSense run inside your own network, on a contract.`,
		features: [
			"Everything in Business, for everyone",
			`More than ${SELF_SERVE_PEOPLE} people, or a site licence`,
			"No egress at all: licensing and job plugins mirrored inside your network",
			"You decide which models and destinations everyone can reach",
			"Virtual desktops and shared servers",
			"A data processing agreement and an audit of the code",
			"Named support on an agreed response time",
		],
		action: [{ label: "Talk to us", href: "/contact" }],
	},
];

/** Answers are quotable definitions, one plain paragraph each, as on the page before Business. */
const FAQ_IS_IT_FREE: PricingQuestion = {
	question: "Is SurfSense free?",
	answer:
		"Yes. The app and all of its updates are free forever, with no account, no trial clock and no usage cap, and reading web pages, YouTube videos and web search come with it. You download it, install it, and use it. A Business licence is needed only to use SurfSense's job plugins for work; everything the app itself does stays free.",
};

export const FAQ_WHAT_BUSINESS_ADDS: PricingQuestion = {
	question: "What does a Business licence add?",
	answer:
		"SurfSense's job plugins, which turn your firm's own files into a finished piece of client work, in the app on your own computer and with the model you choose. The first is the security questionnaire: it answers a customer's security questionnaire in their own spreadsheet from your firm's policies, gives the source of each answer, and lists what needs a person's review. Further jobs join Business as they ship. Business also includes priority support and one feature build request a year. The licence does not lock any of the app's own features, and third-party plugins and MCP servers you add yourself need no licence.",
};

export const FAQ_WHO_NEEDS_BUSINESS: PricingQuestion = {
	question: "Who needs a Business licence?",
	answer:
		"Anyone who uses a SurfSense job plugin for work. Business counts people, not devices: at checkout you say how many people at your firm use job plugins, and at each renewal you confirm the number. A licence for one person is Business Solo. Using the app without the job plugins needs no licence at all.",
};

const FAQ_BUSINESS_PRICE: PricingQuestion = {
	question: "How much does Business cost?",
	answer: `${FIRST} a year for the first person and ${FURTHER} a year for each further person, so 2 people are ${priceFor(2)}, 5 are ${priceFor(5)} and 10 are ${priceFor(10)} a year. It is a founding price: a price change applies only at renewal, after at least 30 days' notice by email. A firm of more than ${SELF_SERVE_PEOPLE} people, or one that needs SurfSense run inside its own network, can ask about Enterprise.`,
};

export const FAQ_BUSINESS_TRIAL: PricingQuestion = {
	question: "Is there a free trial?",
	answer:
		"Yes, one. A 14-day trial of the full job comes with the free app and needs only an email address, with no card and no account. You enter your email on the download page, receive a licence file, import it in Settings › License, and the job plugins are unlocked for 14 days. Each email address gets one trial.",
};

export const FAQ_BUSINESS_RENEWAL: PricingQuestion = {
	question: "Does Business renew automatically?",
	answer:
		"Yes. Business renews every year until you cancel: Stripe charges the card you paid with, and the renewal extends the licence you already have, on the same key. An app that is allowed online fetches the renewed licence file itself, and an offline computer imports the file we email you. The checkout states the yearly renewal before you pay.",
};

export const FAQ_CANCEL_OR_CHANGE: PricingQuestion = {
	question: "How do I cancel, or change the number of people?",
	answer:
		"In Stripe's customer portal, through a link sent to your email, so there is no SurfSense account to sign in to. There you can cancel the renewal or change how many people the licence covers. Cancelling never disables the app.",
};

export const FAQ_BUSINESS_LAPSE: PricingQuestion = {
	question: "What happens when my licence lapses?",
	answer:
		"The app keeps working. A lapse never disables SurfSense: your documents, your index and everything the free app does carry on exactly as before. The job plugins keep running for 30 days after a Business licence lapses. After that new job runs stop, and every file, library and finished output stays readable.",
};

export const FAQ_BUSINESS_NO_ACCOUNT: PricingQuestion = {
	question: "Do I need an account to buy?",
	answer:
		"No. There is no account anywhere in the purchase flow. Checkout collects an email address, the licence file is sent to it and also offered on the confirmation page, and you can have it resent to that same address at any time. Renewal, cancellation and changes to the number of people go through Stripe and the links it sends to that address.",
};

const FAQ_BUSINESS_FEATURE_REQUEST: PricingQuestion = {
	question: "What is a feature build request?",
	answer: `A Business licence includes one feature build request per licence year. You email it to ${EMAIL} from the address the licence is registered to, and we reply within 5 business days with yes or no and the scope we would build. If it fits about a week of engineering work and the direction of the product, it goes to the top of the queue and ships in the open-source app for everyone. There is no fixed delivery date, and if we decline a request you can send another one instead.`,
};

const FAQ_BUSINESS_ENTERPRISE: PricingQuestion = {
	question: "What do you offer enterprises?",
	answer: `Enterprise is for firms of more than ${SELF_SERVE_PEOPLE} people, and for deployments Business does not cover: SurfSense run with no egress at all, with licensing and the job plugins mirrored inside your own network, on virtual desktops or shared servers, with a data processing agreement, an audit of the code and named support on an agreed response time. Pricing comes out of a conversation and is invoiced annually against a contract. Google's comparable product, NotebookLM Enterprise, publishes no price either, and is sold through Google Cloud in subscriptions of 15 to 5,000 licences.`,
};

const FAQ_WHAT_HAPPENED_TO_INDIVIDUAL: PricingQuestion = {
	question: "What happened to the scraper plugins and the Individual licence?",
	answer:
		"They retired when Business went on sale. Reading web pages, YouTube and web search moved into the app, free for everyone, and the plugins for Google Maps, Amazon, Walmart, TikTok, Indeed, Reddit and Instagram stopped. The Individual licence is no longer sold: each one already bought became Business Solo on the same key, and renews at the price it was bought at.",
};

export const BUSINESS_PRICING_FAQ: PricingQuestion[] = [
	FAQ_IS_IT_FREE,
	FAQ_WHAT_BUSINESS_ADDS,
	FAQ_WHO_NEEDS_BUSINESS,
	FAQ_BUSINESS_PRICE,
	FAQ_BUSINESS_TRIAL,
	FAQ_BUSINESS_RENEWAL,
	FAQ_CANCEL_OR_CHANGE,
	FAQ_BUSINESS_LAPSE,
	FAQ_BUSINESS_NO_ACCOUNT,
	FAQ_BUSINESS_FEATURE_REQUEST,
	FAQ_BUSINESS_ENTERPRISE,
	FAQ_WHAT_HAPPENED_TO_INDIVIDUAL,
	FAQ_NOTEBOOKLM_LOCALLY,
];

/** `Product` with the Free and Business offers; Enterprise is quoted, so it has none. */
export const BUSINESS_PRICING_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "Product",
	name: "SurfSense",
	description:
		"A private, open-source research notebook that runs on your own machine. The app is free; a Business licence adds the job plugins, priced per person.",
	url: "https://www.surfsense.com/pricing",
	brand: { "@type": "Brand", name: "SurfSense" },
	offers: [
		{
			"@type": "Offer",
			name: "Free",
			price: 0,
			priceCurrency: "USD",
			description:
				"The full app and every update on Windows, macOS and Linux, forever, with web pages, YouTube and web search as sources and a 14-day trial of the job. No account, runs offline, bring your own model keys.",
		},
		{
			"@type": "Offer",
			name: "Business",
			price: FIRST_PERSON_PRICE,
			priceCurrency: "USD",
			url: `https://www.surfsense.com${BUSINESS_CHECKOUT_URL}`,
			description: `The job plugins, starting with the security questionnaire, for the first person for a year; each further person is ${FURTHER} a year. Renews yearly until cancelled, at a founding price that can change only at renewal, after at least 30 days' notice by email.`,
		},
	],
};
