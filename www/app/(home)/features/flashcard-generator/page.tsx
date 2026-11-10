import { BreadcrumbNav } from "@/components/site/breadcrumb-nav";
import { JsonLd } from "@/components/site/json-ld";
import { FLASHCARDS_URL, STUDENTS_URL, STUDY_GUIDE_URL } from "@/components/site/site-content";
import { Cards01Icon, File02Icon, Mic01Icon, Notebook01Icon } from "@/components/ui/icons";
import {
	type AudiencePageMeta,
	audiencePageMetadata,
	audiencePageSchema,
} from "@/features/audience-pages/audience-metadata";
import {
	AudienceCards,
	AudienceHero,
	type AudienceQuestion,
	AudienceQuestions,
	AudienceSteps,
} from "@/features/audience-pages/audience-sections";

/**
 * The flashcard generator. Brief: `plans/community-local/seo/02-page-briefs.md`,
 * "Flashcards", with the title's dash taken out as every string on this site is.
 *
 * It wins on the "from PDF" and "from notes" forms, not the `flashcard generator` head that
 * Quizlet and its peers own. Studio's flashcards have no download, so the page promises no
 * Anki export, and says so when asked.
 */

const PAGE: AudiencePageMeta = {
	path: FLASHCARDS_URL,
	title: "AI Flashcard Generator From PDFs and Notes, Offline and Free",
	description:
		"Make flashcards from your PDFs, notes, slides and lecture recordings, free and on your own laptop. No account, and it works offline.",
	keywords: [
		"ai flashcard generator",
		"ai flashcard maker",
		"pdf to flashcards",
		"turn notes into flashcards",
		"make flashcards from notes",
		"notebooklm flashcards",
		"flashcards for revision",
	],
	imageAlt: "SurfSense flashcard generator",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is the flashcard generator free?",
		answer:
			"Yes. SurfSense and every update are free, with no account and no usage cap. You only pay a provider if you choose to connect a hosted model of your own.",
	},
	{
		question: "Can I export the flashcards to Anki?",
		answer:
			"Not yet. Flashcards are studied in the app, where your marks are saved as you go, and they have no download.",
	},
	{
		question: "Can it make flashcards from a lecture recording?",
		answer:
			"Yes, once you download a speech recognition model in Settings › Speech recognition. SurfSense transcribes the recording on your laptop, and the transcript becomes a source like any other.",
	},
];

export default function FlashcardGeneratorPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "EducationalApplication")} />
			<BreadcrumbNav
				className="flex justify-center pt-8"
				items={[
					{ name: "Study guide maker", href: STUDY_GUIDE_URL },
					{ name: "Flashcard generator", href: FLASHCARDS_URL },
				]}
			/>

			<AudienceHero
				badge="Flashcard generator"
				title="Make flashcards from your PDFs, notes and"
				highlight="lectures"
				lede="SurfSense makes a flashcard deck from the sources you pick: PDFs, Word files, slides, notes and recordings of your lectures. You go through it one card at a time, mark each one Got it or Needs review, and shuffle. It's free, it runs on your own laptop, and with the free local model nothing is sent anywhere."
				link={{ label: "Make a full study guide", href: STUDY_GUIDE_URL }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to make flashcards with SurfSense"
				steps={[
					{
						title: "Add your material",
						body: "Add readings, slides, notes or a lecture recording to Sources, and wait until they're ready.",
					},
					{
						title: "Tick a topic",
						body: "Tick the sources for the topic you want cards on. Studio uses the same ticks.",
					},
					{
						title: "Click Flashcards",
						body: "In Studio, click Flashcards, write a prompt if you like, such as “only the definitions”, and click Generate.",
					},
					{
						title: "Study the deck",
						body: "Open it from Artifacts, mark each card Got it or Needs review, and use Shuffle. Your marks are saved as you go.",
					},
				]}
			/>

			<AudienceCards
				badge="Why make them here"
				headline="Flashcards from your own material, not someone else's deck"
				cards={[
					{
						heading: "Turn notes into flashcards",
						icon: Notebook01Icon,
						body: "Notes, readings and slides become front-and-back cards on the key terms, definitions, facts and figures.",
					},
					{
						heading: "PDF to flashcards, scans included",
						icon: File02Icon,
						body: "SurfSense reads text PDFs and scanned pages alike, so a photographed handout becomes a deck too.",
					},
					{
						heading: "Flashcards from a lecture recording",
						icon: Mic01Icon,
						body: "Add the recording and SurfSense transcribes it on your laptop, then makes cards from what was said.",
					},
					{
						heading: "Flashcards for revision",
						icon: Cards01Icon,
						body: "Make a deck per topic before an exam, go back to the cards you marked Needs review, and shuffle to test yourself.",
						link: { label: "More for students", href: STUDENTS_URL },
					},
				]}
			/>

			<AudienceQuestions heading="Questions about the flashcard generator" questions={QUESTIONS} />
		</>
	);
}
