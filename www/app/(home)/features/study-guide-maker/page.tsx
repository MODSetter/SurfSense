import Link from "next/link";
import { JsonLd } from "@/components/site/json-ld";
import {
	FLASHCARDS_URL,
	QUIZ_URL,
	STUDY_GUIDE_URL,
	TEACHERS_URL,
} from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { BubbleChatIcon, File02Icon, Notebook01Icon, WifiOffIcon } from "@/components/ui/icons";
import {
	type AudiencePageMeta,
	audiencePageMetadata,
	audiencePageSchema,
} from "@/features/audience-pages/audience-metadata";
import {
	AudienceCards,
	AudienceHero,
	AudienceNotes,
	type AudienceQuestion,
	AudienceQuestions,
	AudienceSteps,
} from "@/features/audience-pages/audience-sections";

/**
 * The study guide maker, the hub of the study pages. Brief:
 * `plans/community-local/seo/02-page-briefs.md`, "Study guide (hub)", with the title's dash
 * taken out as every string on this site is.
 *
 * There is no study guide format: the page sells Studio's summary, flashcards and quiz made
 * from one set of sources, which is what the top result for `study guide maker` promises.
 * The flashcard and quiz pages name this one as their parent in their breadcrumbs.
 */

const PAGE: AudiencePageMeta = {
	path: STUDY_GUIDE_URL,
	title: "Study Guide Maker From Your Notes and PDFs, Free and Offline",
	description:
		"Turn your notes, PDFs and slides into a summary, flashcards and a practice quiz, free and on your own laptop. No account, and it works offline.",
	keywords: [
		"study guide maker",
		"study guide generator",
		"ai study guide maker",
		"ai study tools",
		"notebooklm for studying",
		"ai study guide",
	],
	imageAlt: "SurfSense study guide maker",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is the study guide maker free?",
		answer:
			"Yes. SurfSense and every update are free, with no account and no usage cap. You only pay a provider if you choose to connect a hosted model of your own.",
	},
	{
		question: "Does it work offline?",
		answer:
			"Yes. Once the local model you pick on first launch is downloaded, the summary, the flashcards and the quiz are all made on your laptop with no network connection.",
	},
	{
		question: "What can I make a study guide from?",
		answer:
			"PDF, Word, PowerPoint and Excel files, scanned pages and photos, which SurfSense reads with text recognition, and recordings, which it transcribes on your laptop once you download a speech recognition model.",
	},
];

export default function StudyGuideMakerPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "EducationalApplication")} />

			<AudienceHero
				badge="Study guide maker"
				title="Turn your notes and PDFs into a study guide, flashcards and"
				highlight="a quiz"
				lede="SurfSense makes a study guide from the PDFs, Word files, slides and notes you already have: a written summary, a flashcard deck and a practice quiz, all from the same sources. It runs on your own laptop, it's free, and with the free local model nothing is sent anywhere."
				link={{ label: "Make flashcards", href: FLASHCARDS_URL }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to make a study guide with SurfSense"
				steps={[
					{
						title: "Add your material",
						body: "Add lecture slides, readings and notes to Sources, as PDF, Word or PowerPoint files, scans or recordings.",
					},
					{
						title: "Tick what you're revising",
						body: "Tick the sources for one topic or one exam. Chat and Studio share the same ticks.",
					},
					{
						title: "Make the summary",
						body: "In Studio, click Markdown or Word, write a prompt if you like, such as “a study guide with the key terms”, and click Generate.",
					},
					{
						title: "Add flashcards and a quiz",
						body: "Click Flashcards, then Quiz, on the same sources. Each appears in the Artifacts list when it's ready.",
					},
				]}
			/>

			<AudienceCards
				badge="Questions students ask"
				headline="Study guides, answered"
				cards={[
					{
						heading: "Can AI create study guides from PDFs?",
						icon: File02Icon,
						body: "Yes. SurfSense reads your PDFs, scanned pages included, and writes a summary of the parts you pick, with a flashcard deck and a quiz from the same pages.",
						link: { label: "Quiz generator", href: QUIZ_URL },
					},
					{
						heading: "How can I create my own study guide?",
						icon: Notebook01Icon,
						body: "By hand: list the key terms and ideas of each topic, summarise them in your own words, and test yourself. SurfSense drafts all three from your sources, so your time goes on checking and learning.",
					},
					{
						heading: "Can ChatGPT create a study guide?",
						icon: BubbleChatIcon,
						body: "Yes, from what you paste or upload, which goes to OpenAI's servers. SurfSense makes one from every source you tick, on your own laptop, and keeps it in your workspace with the rest.",
					},
					{
						heading: "NotebookLM for studying, offline",
						icon: WifiOffIcon,
						body: "SurfSense works like NotebookLM: add sources, ask questions with citations, and make study material from them. It runs on your laptop instead of Google's servers, needs no Google account, and works offline with a local model.",
					},
				]}
			/>

			<AudienceNotes heading="For teachers: a study guide for the whole class">
				<p>
					The same steps make a study guide for a class: a summary of the unit, a deck of flashcards
					and a quiz to check it, from your own materials.{" "}
					<Link className={siteText.link} href={TEACHERS_URL}>
						See what SurfSense does for teachers
					</Link>
					.
				</p>
			</AudienceNotes>

			<AudienceQuestions heading="Questions about the study guide maker" questions={QUESTIONS} />
		</>
	);
}
