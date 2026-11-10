import { JsonLd } from "@/components/site/json-ld";
import {
	FLASHCARDS_URL,
	PODCAST_URL,
	QUIZ_URL,
	STUDENTS_URL,
	STUDY_GUIDE_URL,
} from "@/components/site/site-content";
import {
	Cards01Icon,
	NetworkIcon,
	Notebook01Icon,
	PodcastIcon,
	Presentation02Icon,
	Quiz02Icon,
} from "@/components/ui/icons";
import {
	type AudiencePageMeta,
	audiencePageMetadata,
	audiencePageSchema,
} from "@/features/audience-pages/audience-metadata";
import {
	AudienceAnswer,
	AudienceCards,
	AudienceHero,
	AudienceNotes,
	type AudienceQuestion,
	AudienceQuestions,
} from "@/features/audience-pages/audience-sections";

/**
 * AI for students. Brief: `plans/community-local/seo/09-audience-pages.md`, `/ai-for-students`.
 *
 * Free distribution: it names no paid job, so it exists with or without the Business switch.
 * It promises only what Studio makes today, in the user guide's words (`content/docs/v2/`),
 * and never more than the free local model can be expected to do: the guide says strong
 * models make richer Word documents and PDFs, and the page says so too.
 *
 * Study demand peaks in March and April, so it should be indexed by early January.
 */

const PAGE: AudiencePageMeta = {
	path: STUDENTS_URL,
	title: "Free AI for Students: Flashcards, Quizzes and Study Guides",
	description:
		"Turn your notes and PDFs into flashcards, quizzes, mind maps and podcasts, free and on your own laptop. A NotebookLM-style notebook with no account.",
	keywords: [
		"ai for students",
		"free ai for students",
		"ai study tool",
		"study guide maker",
		"ai flashcard maker",
		"ai quiz generator",
		"notebooklm for students",
	],
	imageAlt: "SurfSense, free AI for students",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is SurfSense free for students?",
		answer:
			"Yes. The app and every update are free, with no account, no subscription and no usage cap. You only pay a provider if you choose to connect a hosted model of your own.",
	},
	{
		question: "Does it work without internet?",
		answer:
			"Yes. Once the local model you pick on first launch is downloaded, you can add files, ask questions and make flashcards, quizzes and podcasts with no network connection.",
	},
	{
		question: "Can it read my lecture slides and scans?",
		answer:
			"Yes. SurfSense reads PDF, Word, PowerPoint and Excel files, and reads scanned pages and photos with text recognition. A recording, such as a lecture, is transcribed on your laptop once you download a speech recognition model in Settings › Speech recognition.",
	},
	{
		question: "Are my files uploaded anywhere?",
		answer:
			"Your files and everything SurfSense makes stay in a folder on your laptop. With a local model nothing is sent anywhere. With a hosted model you connect, that provider receives what each request needs.",
	},
	{
		question: "Is SurfSense the same as NotebookLM?",
		answer:
			"It works the same way: add sources, ask questions with citations, and make study material from them. NotebookLM runs on Google's servers and needs a Google account. SurfSense runs on your own laptop with no account, and works offline with a local model.",
	},
];

export default function AiForStudentsPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "EducationalApplication")} />

			<AudienceHero
				badge="AI for students"
				title="Free AI for students: turn your notes and PDFs into flashcards, quizzes and"
				highlight="study guides"
				lede="SurfSense is a free, open-source study app that runs on your own laptop. Add your lecture slides, readings, notes and recordings, ask questions with a citation for every point, and make flashcards, practice quizzes, mind maps and podcasts from them. With the free local model, nothing is sent anywhere."
				note="No account, no subscription and no usage cap."
				link={{ label: "Make a study guide", href: STUDY_GUIDE_URL }}
			/>

			<AudienceCards
				badge="What it makes"
				headline="Everything a study session needs, from your own material"
				cards={[
					{
						heading: "Flashcards from your notes and PDFs",
						icon: Cards01Icon,
						body: "Studio makes a deck you go through one card at a time, marking each one Got it or Needs review, with Shuffle. Your marks are saved as you go.",
						link: { label: "Flashcard generator", href: FLASHCARDS_URL },
					},
					{
						heading: "Practice quizzes from your readings",
						icon: Quiz02Icon,
						body: "Multiple-choice questions with an explanation for every answer, a score, and Retake quiz for all of them or only the ones you missed.",
						link: { label: "Quiz generator", href: QUIZ_URL },
					},
					{
						heading: "A study guide from one set of sources",
						icon: Notebook01Icon,
						body: "Tick the chapters you are revising, then make a written summary, a flashcard deck and a quiz from the same sources.",
						link: { label: "Study guide maker", href: STUDY_GUIDE_URL },
					},
					{
						heading: "Turn a chapter into a podcast to listen to",
						icon: PodcastIcon,
						body: "Pick a style and a length, from about 3 to about 15 minutes, and SurfSense voices it on your laptop with the voice model it ships.",
						link: { label: "Podcast generator", href: PODCAST_URL },
					},
					{
						heading: "Mind maps of a topic",
						icon: NetworkIcon,
						body: "An outline of your sources drawn as a map you can expand, to see how the ideas fit together before an exam.",
					},
					{
						heading: "Slides for a class presentation",
						icon: Presentation02Icon,
						body: "A PowerPoint deck from your research, ready to edit in PowerPoint, Keynote or Google Slides.",
					},
				]}
			/>

			<AudienceAnswer
				heading="Like NotebookLM, on your own laptop"
				points={[
					"No account or subscription",
					"Works offline with a local model",
					"Your files stay in a folder on your laptop",
					"Free forever, and open source",
				]}
			>
				<p>
					SurfSense works the way NotebookLM does: add your sources, ask questions with a citation
					for every point, and turn the sources into study material. The difference is where it
					runs. SurfSense is an app on your own laptop, with no Google account and no usage limits.
				</p>
				<p>
					With the free local model, nothing you add is sent anywhere. If you want a bigger model,
					you can connect a hosted one with your own key, and that provider receives what each
					request needs.
				</p>
			</AudienceAnswer>

			<AudienceNotes heading="Revision flashcards and quizzes, for exams">
				<p>
					Make a flashcard deck and a practice quiz for each topic. Go back to the cards you marked
					Needs review, and retake the quiz with only the questions you missed, until there are none
					left.
				</p>
			</AudienceNotes>

			<AudienceNotes heading="What you need to run it">
				<p>
					A Windows PC, a Mac with Apple silicon, or a Linux computer. On first launch, SurfSense
					offers a small model that runs on your laptop's processor, free, with no internet needed
					once it is downloaded. A bigger local model, or a key for a hosted one, makes richer Word
					documents and PDFs.
				</p>
				<p>
					Podcasts use the voice model SurfSense ships, so they work offline too. A recording, such
					as a lecture, is transcribed on your laptop once you download a speech recognition model
					in Settings › Speech recognition.
				</p>
			</AudienceNotes>

			<AudienceQuestions heading="Questions students ask" questions={QUESTIONS} />
		</>
	);
}
