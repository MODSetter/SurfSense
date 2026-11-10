import Link from "next/link";
import { notFound } from "next/navigation";
import { JsonLd } from "@/components/site/json-ld";
import { ACCOUNTANTS_URL, SECURITY_QUESTIONNAIRE_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import {
	BookOpen01Icon,
	CheckmarkBadgeIcon,
	ClipboardCheckIcon,
	File02Icon,
} from "@/components/ui/icons";
import {
	type AudiencePageMeta,
	audiencePageSchema,
	businessPageMetadata,
} from "@/features/audience-pages/audience-metadata";
import {
	AudienceAnswer,
	AudienceCards,
	AudienceClosing,
	AudienceHero,
	AudienceNotes,
	type AudienceQuestion,
	AudienceQuestions,
	AudienceSteps,
} from "@/features/audience-pages/audience-sections";
import { BUSINESS_LAUNCHED } from "@/features/business-launch/business-launched.mts";
import { FIRST_PERSON_PRICE, yearlyPriceLabel } from "../../pricing/business-price";
import { BUSINESS_CHECKOUT_URL } from "../../pricing/business-pricing-content";

/**
 * The security questionnaire job. Brief: `plans/community-local/seo/09-audience-pages.md`,
 * `/jobs/security-questionnaire`. What the job does, and every label quoted here, comes
 * from the user guide's "Run a job" and "What a job writes" (`content/docs/v2/jobs.mdx`),
 * so the two never disagree.
 *
 * A 404 until Business is on sale (`NEXT_PUBLIC_BUSINESS_LAUNCHED`). Pages for named
 * questionnaires (HECVAT, CAIQ, SIG Lite) follow `08-b2b-artifact-jobs.md` later.
 */

const PRICE = yearlyPriceLabel(FIRST_PERSON_PRICE);

const PAGE: AudiencePageMeta = {
	path: SECURITY_QUESTIONNAIRE_URL,
	title: "Answer Security Questionnaires From Your Own Policies",
	description:
		"SurfSense fills a customer's security questionnaire in their own spreadsheet from your firm's policies, cites each answer and flags what needs a person.",
	keywords: [
		"security questionnaire",
		"security questionnaire automation",
		"vendor security questionnaire",
		"security questionnaire software",
		"answer security questionnaires",
	],
	imageAlt: "SurfSense security questionnaire",
};

export const metadata = businessPageMetadata(BUSINESS_LAUNCHED, PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "What does the security questionnaire need?",
		answer:
			"The questionnaire as an Excel workbook (.xlsx), your firm's policies in Sources, a chat model selected in Settings, and a Business licence or its 14-day trial. Save a Word or older Excel file as .xlsx first.",
	},
	{
		question: "Will it make up answers?",
		answer:
			"No. It answers from the documents you tick. It writes Yes only where a passage in them says so, word for word, and a second check agrees, and it leaves any question it can't back for a person.",
	},
	{
		question: "What are suggested answers?",
		answer:
			"Answers SurfSense found passages for but leaves for you to choose. They're on the exceptions sheet with the rest of what a person should look at. Once you've checked them, confirm them in Jobs or in Studio, and each one is written into its cell in a new version of the copy.",
	},
	{
		question: "Which model should I use?",
		answer:
			"The job answers with the chat model selected in Settings. A model that runs on your computer keeps your documents on it, but it is usually smaller and leaves more questions for a person to answer.",
	},
	{
		question: "Are my policies uploaded anywhere?",
		answer:
			"Running a job sends SurfSense nothing. The questionnaire and your policies are read on your computer, and go only to the models you chose for the job, when they don't run on your computer.",
	},
];

export default function SecurityQuestionnairePage() {
	if (!BUSINESS_LAUNCHED) notFound();

	return (
		<>
			<JsonLd
				data={audiencePageSchema(PAGE, {
					price: FIRST_PERSON_PRICE,
					checkoutPath: BUSINESS_CHECKOUT_URL,
				})}
			/>

			<AudienceHero
				badge="Security questionnaire"
				title="Answer a security questionnaire in the customer's own spreadsheet, from"
				highlight="your own policies"
				lede="Add the questionnaire a customer sent you, as an Excel workbook, and your firm's policies. SurfSense fills in a copy, gives the source of each answer, and leaves what it can't back with a quote for a person to check."
				note="A job plugin that comes with SurfSense Business. Try it free for 14 days."
				link={{ label: "See pricing", href: "/pricing" }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to answer a security questionnaire with SurfSense"
				steps={[
					{
						title: "Add the questionnaire and your policies",
						body: "Add the workbook (.xlsx) and your firm's policies to Sources, and wait until they're ready. Save a Word or older Excel file as .xlsx first.",
					},
					{
						title: "Run the security questionnaire",
						body: "In Jobs, choose Run beside Security questionnaire. Pick the workbook under Workbook to fill in, tick your documents under Your firm’s documents to answer from, and choose Start.",
					},
					{
						title: "Let it work through the questions",
						body: "Jobs shows how far the run has got, then how many questions SurfSense answered, how many need a person, and how many suggested answers wait for you.",
					},
					{
						title: "Check the copy and download it",
						body: "Open the copy in Studio, check SurfSense's two sheets, confirm the suggested answers you agree with, and download it with With changes.",
					},
				]}
			/>

			<AudienceCards
				badge="What it writes"
				headline="A filled-in copy, with the source of every answer"
				cards={[
					{
						heading: "Answers in the customer's own cells",
						icon: ClipboardCheckIcon,
						body: "Each answer goes in its own cell, spelled as the cell's dropdown spells it. Hidden rows and columns, and rows that are locked or already answered, are left as they were.",
					},
					{
						heading: "The source of every answer",
						icon: BookOpen01Icon,
						body: "A comment and the answer's source go in the workbook's own comment and evidence columns, where they're empty.",
					},
					{
						heading: "Yes only where your policies say so",
						icon: CheckmarkBadgeIcon,
						body: "SurfSense writes Yes only where a passage in your documents says so, word for word, and a second check agrees. A question it can't back is left for a person.",
					},
					{
						heading: "An answers sheet and an exceptions sheet",
						icon: File02Icon,
						body: "Two sheets of its own after yours: each answer's source and the quote it rests on, and every question a person should look at, and why. Delete them before you send the file if the customer shouldn't see them.",
					},
				]}
			/>

			<AudienceAnswer
				heading="SurfSense never receives your policies"
				points={[
					"Runs in the app on your computer",
					"Sends SurfSense nothing",
					"Never changes your own file",
					"Works with a local model or your firm's key",
				]}
			>
				<p>
					Running a job sends SurfSense nothing. The questionnaire and your policies are read on
					your computer, and go only to the models you chose for the job, the one that answers and
					the one that checks, when they don't run on your computer.
				</p>
				<p>
					Each run makes a revised copy in Studio, and your own file is never changed. Earlier
					versions of the copy stay in Studio too.
				</p>
			</AudienceAnswer>

			<AudienceNotes heading="Which questionnaires it fills in">
				<p>
					Any questionnaire that arrives as an Excel workbook with a column of questions and a
					column for answers, or answer dropdowns. A workbook in which SurfSense finds no questions
					stops the run at once.
				</p>
				<p>
					Each run fills in one workbook. While it runs you can keep working, as long as SurfSense
					stays open, and choosing Cancel run stops it with nothing written.
				</p>
			</AudienceNotes>

			<AudienceClosing
				badge="Pricing"
				heading="Comes with Business, free for 14 days"
				link={{ label: "See pricing", href: "/pricing" }}
			>
				<p>
					The security questionnaire is a job plugin in SurfSense Business, with the contract
					redline, at {PRICE} a year for each person who uses them. A 14-day trial of both needs
					only an email address, with no card and no account. Run an accounting firm?{" "}
					<Link className={siteText.link} href={ACCOUNTANTS_URL}>
						See what else SurfSense does for accountants
					</Link>
					.
				</p>
			</AudienceClosing>

			<AudienceQuestions
				heading="Questions about the security questionnaire"
				questions={QUESTIONS}
			/>
		</>
	);
}
