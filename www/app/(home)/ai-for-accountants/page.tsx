import { JsonLd } from "@/components/site/json-ld";
import { ACCOUNTANTS_URL, SECURITY_QUESTIONNAIRE_URL } from "@/components/site/site-content";
import {
	BubbleChatIcon,
	ChartHistogramIcon,
	Presentation02Icon,
	SecurityCheckIcon,
} from "@/components/ui/icons";
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
import { UseCaseSection } from "@/features/guides/use-case-section";
import { FIRST_PERSON_PRICE, yearlyPriceLabel } from "../pricing/business-price";

/**
 * AI for accountants. Brief: `plans/community-local/seo/09-audience-pages.md`,
 * `/ai-for-accountants`.
 *
 * The exact phrases draw little search (about 50 a month in clickstream; Google's 6,600 for
 * `ai for accountants` has absorbed accounting-software searches), so this page is where
 * outreach, trial emails and demos send accounting firms as much as a search page.
 *
 * It sells the security questionnaire. Any line on what a regulator requires of a firm goes through a
 * compliance read first; this page says only where the data is.
 */

const PRICE = yearlyPriceLabel(FIRST_PERSON_PRICE);

const PAGE: AudiencePageMeta = {
	path: ACCOUNTANTS_URL,
	title: "AI for Accountants: Private AI for Client Financial Files",
	description:
		"Free, open-source AI for accountants that keeps client files on your computer. Draft reports, pull figures and answer security questionnaires.",
	keywords: [
		"ai for accountants",
		"ai for accounting firms",
		"ai for bookkeepers",
		"ai for cpa",
		"ai for tax preparers",
		"ai for audit",
		"private ai for accountants",
	],
	imageAlt: "SurfSense, private AI for accountants",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Does SurfSense connect to QuickBooks or Xero?",
		answer:
			"No. SurfSense reads the files you add: PDF, Word, Excel and PowerPoint files, scans and photos, and web pages. Export a report from your accounting software as a PDF or an Excel file, and add it to Sources.",
	},
	{
		question: "Is client data uploaded?",
		answer:
			"Not with a local model: SurfSense keeps your files, its index and your chats on your computer, and sends nothing. With a hosted model you choose, that provider receives only what each request needs, such as the question and the passages behind it.",
	},
	{
		question: "Is SurfSense free for an accounting firm?",
		answer: `Yes. The app and every update are free for any use, client work included. A Business licence is needed only for SurfSense's job plugins, such as the security questionnaire, at ${PRICE} a year for each person who uses them.`,
	},
	{
		question: "Does SurfSense work offline?",
		answer:
			"Yes, with a local model. SurfSense installs with a model runner built in, and once a model is downloaded it answers questions about the sources you already added with no network connection. A hosted model needs the internet.",
	},
];

export default function AiForAccountantsPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE)} />

			<AudienceHero
				badge="AI for accountants"
				title="Private AI for accountants: client files stay on"
				highlight="your computer"
				lede="SurfSense is a free, open-source AI app that runs on your own computer. Add returns, statements, ledgers and engagement letters, ask questions with a citation for every point, and turn them into reports, spreadsheets and client decks. With a local model, nothing is sent anywhere."
				note="Business adds the security questionnaire, for the clients who send you one, with a 14-day free trial."
				link={{ label: "See pricing", href: "/pricing" }}
			/>

			<UseCaseSection
				badge="See it work"
				headline="Watch it work through a client's files"
				slugs={[
					"ask-and-cite",
					"analyse-a-spreadsheet",
					"agent-documents",
					"security-questionnaire",
				]}
				placement="for-page"
			/>

			<AudienceAnswer
				heading="Can accountants use AI with client financial data?"
				points={[
					"Client files stay in a folder you control",
					"No SurfSense account, server or copy",
					"A local model sends nothing anywhere",
					"A hosted model gets only what a request needs",
					"Open source, so your IT provider can check it",
				]}
			>
				<p>
					It turns on where the data goes, so here is exactly where it goes. SurfSense keeps its
					index, your chats and everything it makes in a folder on your computer. There is no
					SurfSense account and no SurfSense server, so we never hold a copy of a client's figures.
				</p>
				<p>
					With a model that runs on your computer, nothing leaves it. With a hosted model you
					choose, that provider receives only what each request needs: the question and the passages
					behind it, or the documents you ask Studio to work from.
				</p>
				<p>
					Whether a workflow fits your firm's own security plan and obligations is yours to judge.
					What SurfSense can tell you is where every file is.
				</p>
			</AudienceAnswer>

			<AudienceCards
				badge="What it does"
				headline="From the client's documents to the finished work"
				cards={[
					{
						heading: "Ask across a client's documents, with citations",
						icon: BubbleChatIcon,
						body: "Add statements, returns, ledgers and letters as PDF, Excel or Word files, or as scans. Every point in an answer cites the passage behind it, so you can check a figure before you use it.",
					},
					{
						heading: "Pull the figures into a spreadsheet",
						icon: ChartHistogramIcon,
						body: "Studio turns the tables in your sources into an Excel workbook you can check and edit, from the documents you pick.",
					},
					{
						heading: "Client-ready reports, letters and decks",
						icon: Presentation02Icon,
						body: "Studio makes editable Word reports, PDFs and PowerPoint decks from the documents you pick. They are real Office files, ready for your letterhead.",
					},
					{
						heading: "Answer a client's security questionnaire",
						icon: SecurityCheckIcon,
						body: "When a client sends a security questionnaire as an Excel workbook, the security questionnaire job fills it in from your firm's policies and gives the source of each answer. It comes with Business.",
						link: {
							label: "How the security questionnaire works",
							href: SECURITY_QUESTIONNAIRE_URL,
						},
					},
				]}
			/>

			<AudienceClosing
				badge="Pricing"
				heading="Free for every accountant. Business adds the jobs."
				link={{ label: "See pricing", href: "/pricing" }}
			>
				<p>
					The app and every update are free, with no account and no usage cap. A Business licence
					adds SurfSense's job plugins, the security questionnaire and the contract redline, at{" "}
					{PRICE} a year for each person who uses them. You can try both free for 14 days.
				</p>
			</AudienceClosing>

			<AudienceQuestions heading="Questions accountants ask" questions={QUESTIONS} />
		</>
	);
}
