import { JsonLd } from "@/components/site/json-ld";
import { CONTRACT_REDLINE_URL, LAWYERS_URL } from "@/components/site/site-content";
import { BubbleChatIcon, CpuIcon, File02Icon, LegalDocument01Icon } from "@/components/ui/icons";
import {
	type AudiencePageMeta,
	audiencePageMetadata,
	audiencePageSchema,
} from "@/features/audience-pages/audience-metadata";
import {
	AudienceAnswer,
	AudienceCards,
	AudienceClosing,
	AudienceHero,
	type AudienceQuestion,
	AudienceQuestions,
} from "@/features/audience-pages/audience-sections";
import { FIRST_PERSON_PRICE, yearlyPriceLabel } from "../pricing/business-price";

/**
 * AI for lawyers. Brief: `plans/community-local/seo/09-audience-pages.md`, `/ai-for-lawyers`.
 *
 * It sells the contract redline. ADR 0086 holds legal marketing for a lawyer's review:
 * record who read this page before the release that ships it.
 *
 * Two rules from the brief constrain edits: say where the bytes are, never what professional
 * rule that satisfies, and quote no accuracy figure for the redline before the maintainer has
 * checked the eval's stance file.
 */

const PRICE = yearlyPriceLabel(FIRST_PERSON_PRICE);

const PAGE: AudiencePageMeta = {
	path: LAWYERS_URL,
	title: "AI for Lawyers: Private Legal AI That Runs on Your Computer",
	description:
		"Free, open-source legal AI that keeps client files on your computer. Search a matter, draft memos and decks, and redline contracts against your playbook.",
	keywords: [
		"ai for lawyers",
		"legal ai tools",
		"legal ai",
		"chatgpt for lawyers",
		"ai for law firms",
		"ai contract review",
		"private legal ai",
	],
	imageAlt: "SurfSense, private AI for lawyers",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Does SurfSense give legal advice?",
		answer:
			"No. SurfSense is software that works from the documents you add and, for the contract redline, from your firm's own playbook. It never makes up a position, and every answer cites the passage it came from so you can check it. A lawyer decides what to rely on.",
	},
	{
		question: "How is SurfSense different from using ChatGPT for legal work?",
		answer:
			"ChatGPT runs on OpenAI's servers, so a document you upload to it goes to them. SurfSense is an app on your own computer: it answers from the documents you add, cites the passage behind each point, and with a local model sends nothing anywhere. You can still use an OpenAI model in SurfSense with your firm's own key.",
	},
	{
		question: "Does SurfSense work offline?",
		answer:
			"Yes, with a local model. SurfSense installs with a model runner built in, and once a model is downloaded it answers questions about the sources you already added with no network connection. A hosted model needs the internet.",
	},
	{
		question: "Where are my client files stored?",
		answer:
			"In a folder in your user directory on your own computer, with a database file in it. You can back it up, keep it on an encrypted disk, or delete everything by deleting the folder. SurfSense has no server that keeps a copy.",
	},
	{
		question: "How much does the contract redline cost?",
		answer: `It comes with a Business licence, at ${PRICE} a year for each person who uses SurfSense's job plugins, and a 14-day free trial needs only an email address. Everything else in the app is free.`,
	},
];

export default function AiForLawyersPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE)} />

			<AudienceHero
				badge="AI for lawyers"
				title="Private AI for lawyers: client files stay on"
				highlight="your computer"
				lede="SurfSense is a free, open-source AI app that runs on your own computer. Add a matter's documents, ask questions across them with a citation for every point, and turn them into memos, chronologies and decks. With a local model, nothing is sent anywhere."
				note="No account, and no vendor copy of your files. Business adds the contract redline, with a 14-day free trial."
				link={{ label: "See pricing", href: "/pricing" }}
			/>

			<AudienceAnswer
				heading="Can lawyers use AI with client documents?"
				points={[
					"The index and your chats stay in a folder you control",
					"No SurfSense account, server or copy",
					"A local model sends nothing anywhere",
					"A hosted model gets only what a request needs",
					"Open source, so your IT team can check it",
				]}
			>
				<p>
					It turns on where the documents go, so here is exactly where they go. SurfSense keeps its
					index, your chats and everything it makes in a folder on your computer. There is no
					SurfSense account and no SurfSense server, so we never hold a copy of your files or your
					chats.
				</p>
				<p>
					With a model that runs on your computer, nothing leaves it. With a hosted model you
					choose, such as one your firm already has a contract with, that provider receives only
					what each request needs: the question and the passages behind it, or the documents you ask
					Studio to work from.
				</p>
				<p>
					Whether a workflow meets your professional duties is yours to judge. The ABA's Formal
					Opinion 512 on generative AI tools is a good place to start.
				</p>
			</AudienceAnswer>

			<AudienceCards
				badge="What it does"
				headline="One app for the matter, from the first read to the redline"
				cards={[
					{
						heading: "Ask across a matter, with a citation for every answer",
						icon: BubbleChatIcon,
						body: "Add pleadings, correspondence, transcripts and exhibits as PDF or Word files, or as scans. Ask in plain words, and every point in the answer cites the passage it came from, which opens with a click.",
					},
					{
						heading: "Turn a case file into a memo, a chronology or a deck",
						icon: File02Icon,
						body: "Studio makes an editable Word memo, a spreadsheet of dates and events, or a PowerPoint deck from the documents you pick. They are real Office files, ready to revise and put on letterhead.",
					},
					{
						heading: "Review a contract against your firm's playbook",
						icon: LegalDocument01Icon,
						body: "The contract redline checks a Word contract against your own positions or standard agreement, and returns a copy with tracked changes and a comment on each one. It comes with Business.",
						link: { label: "How the contract redline works", href: CONTRACT_REDLINE_URL },
					},
					{
						heading: "Use the model your firm approves",
						icon: CpuIcon,
						body: "Run a model on your own computer, or connect a provider your firm already uses, such as OpenAI, Anthropic or any OpenAI-compatible service. The model is a setting you can change at any time.",
					},
				]}
			/>

			<AudienceClosing
				badge="Pricing"
				heading="Free for every lawyer. Business adds the jobs."
				link={{ label: "See pricing", href: "/pricing" }}
			>
				<p>
					The app and every update are free, with no account and no usage cap. A Business licence
					adds SurfSense's job plugins, the contract redline and the security questionnaire, at{" "}
					{PRICE} a year for each person who uses them. You can try both free for 14 days.
				</p>
			</AudienceClosing>

			<AudienceQuestions heading="Questions lawyers ask" questions={QUESTIONS} />
		</>
	);
}
