import Link from "next/link";
import { JsonLd } from "@/components/site/json-ld";
import { PODCAST_URL, QUIZ_URL, STUDENTS_URL, TEACHERS_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import {
	Cards01Icon,
	File02Icon,
	NetworkIcon,
	Notebook01Icon,
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
 * AI for teachers. Brief: `plans/community-local/seo/09-audience-pages.md`, `/ai-for-teachers`.
 *
 * Free distribution, with or without the Business switch. Studio has no worksheet or lesson
 * plan format, so the page says what is true: Studio writes a Word or PDF file from the
 * teacher's prompt. Studio's quiz has no download, so a printable test is a Word or PDF file
 * too. It makes no claim about student-data rules (FERPA and the like); it says where the
 * files are and lets the school decide.
 */

const PAGE: AudiencePageMeta = {
	path: TEACHERS_URL,
	title: "Free AI for Teachers: Quizzes, Worksheets and Lesson Plans",
	description:
		"Make quizzes, worksheets, lesson plans and slides from your own teaching materials, free and on your own computer, with no account or school sign-up.",
	keywords: [
		"ai for teachers",
		"ai worksheet generator",
		"ai lesson plan generator",
		"free ai for teachers",
		"ai tools for teachers",
		"ai quiz maker",
		"quiz generator from pdf",
	],
	imageAlt: "SurfSense, free AI for teachers",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is SurfSense free for teachers?",
		answer:
			"Yes. The app and every update are free, with no account and no usage cap, for your classroom or anything else. You only pay a provider if you choose to connect a hosted model of your own.",
	},
	{
		question: "Can I print the quiz?",
		answer:
			"Studio's quiz is made to take in the app, with a score and Retake quiz, and has no download. To print a test, ask Studio for a Word or PDF file with the questions and an answer key.",
	},
	{
		question: "Is student work uploaded anywhere?",
		answer:
			"Not with a local model: SurfSense keeps your files and everything it makes on your computer, and sends nothing. With a hosted model you connect, that provider receives what each request needs, such as the question and the passages behind it.",
	},
	{
		question: "Can my students use it too?",
		answer:
			"Yes, and it is free for them as well. Each student installs SurfSense on their own computer, with no account, and makes their own flashcards and quizzes from their notes.",
	},
];

export default function AiForTeachersPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "EducationalApplication")} />

			<AudienceHero
				badge="AI for teachers"
				title="Free AI for teachers: quizzes, worksheets and lesson plans from your"
				highlight="own materials"
				lede="SurfSense is a free, open-source app that runs on your own computer. Add your syllabus, readings and slides, then make quizzes, worksheets, lesson plans and slide decks from them, or ask questions across them with a citation for every point."
				note="No account, no school sign-up and no subscription."
				link={{ label: "How the quiz generator works", href: QUIZ_URL }}
			/>

			<AudienceCards
				badge="What it makes"
				headline="Class materials from the materials you already have"
				cards={[
					{
						heading: "A quiz from your own materials",
						icon: Quiz02Icon,
						body: "Studio writes multiple-choice questions with an explanation for every answer and a score, to try in the app. For a printable test, ask for a Word or PDF file with an answer key.",
						link: { label: "Quiz generator", href: QUIZ_URL },
					},
					{
						heading: "Worksheets as Word or PDF files",
						icon: File02Icon,
						body: "Tick a chapter and ask Studio for a worksheet, such as ten short questions on it. It writes a Word document or a PDF you can edit and print.",
					},
					{
						heading: "Lesson plans from your syllabus",
						icon: Notebook01Icon,
						body: "Tick the syllabus and the readings for a unit and ask for a lesson plan. Studio writes it as a Word document you can adapt.",
					},
					{
						heading: "Slides for tomorrow's class",
						icon: Presentation02Icon,
						body: "A PowerPoint deck from your notes and readings, ready to edit in PowerPoint, Keynote or Google Slides.",
					},
					{
						heading: "Flashcards and a podcast recap for your students",
						icon: Cards01Icon,
						body: "Make a flashcard deck from a chapter, or a short podcast recap of about 3 minutes, voiced on your computer with the voice model SurfSense ships.",
						link: { label: "Podcast generator", href: PODCAST_URL },
					},
					{
						heading: "Mind maps for a new topic",
						icon: NetworkIcon,
						body: "An outline of a unit's sources drawn as a map you can expand, to show how the ideas connect.",
					},
				]}
			/>

			<AudienceAnswer
				heading="With a local model, student work never leaves your computer"
				points={[
					"No account or school sign-up",
					"Files stay in a folder you control",
					"A local model sends nothing anywhere",
					"Free forever, and open source",
				]}
			>
				<p>
					SurfSense keeps your files, its index and everything it makes in a folder on your
					computer, and has no server of its own. With the free local model, nothing is sent
					anywhere. If you connect a hosted model with your own key, that provider receives what
					each request needs.
				</p>
				<p>
					Whether a tool fits your school's rules on student data is for your school to decide. What
					SurfSense can tell you is where every file is.
				</p>
			</AudienceAnswer>

			<AudienceNotes heading="What you need to run it">
				<p>
					SurfSense runs on Windows, on a Mac with Apple silicon, and on Linux. On first launch it
					offers a small model that runs on your computer's processor, free. A bigger model, or a
					key for a hosted one, makes richer Word documents and PDFs, so use one for worksheets and
					lesson plans if you can.
				</p>
				<p>
					Your students can use it too, free, on their own computers.{" "}
					<Link className={siteText.link} href={STUDENTS_URL}>
						See what SurfSense does for students
					</Link>
					.
				</p>
			</AudienceNotes>

			<AudienceQuestions heading="Questions teachers ask" questions={QUESTIONS} />
		</>
	);
}
