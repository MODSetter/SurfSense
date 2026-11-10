import { BreadcrumbNav } from "@/components/site/breadcrumb-nav";
import { JsonLd } from "@/components/site/json-ld";
import { QUIZ_URL, STUDY_GUIDE_URL, TEACHERS_URL } from "@/components/site/site-content";
import { File02Icon, InformationCircleIcon, Quiz02Icon, TeacherIcon } from "@/components/ui/icons";
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
 * The quiz generator. Brief: `plans/community-local/seo/02-page-briefs.md`, "Quiz", with the
 * title's dash taken out as every string on this site is.
 *
 * "From your own material" is the difference from quiz makers that start from a blank form.
 * Studio's quiz is multiple choice, four options with one right answer and an explanation
 * (`surfsense_local/backend/worker/studio/content/quiz/`), and it has no download, so a
 * printable test is a Word or PDF file.
 */

const PAGE: AudiencePageMeta = {
	path: QUIZ_URL,
	title: "AI Quiz Generator From Your PDFs and Notes, Offline and Free",
	description:
		"Generate a practice quiz from your own PDFs, notes and slides, with an explanation for every answer. Free, on your own laptop, with no account.",
	keywords: [
		"ai quiz generator",
		"ai quiz maker",
		"pdf to quiz",
		"quiz generator from pdf",
		"free ai quiz generator",
		"practice test generator",
		"ai question generator",
	],
	imageAlt: "SurfSense quiz generator",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is the quiz generator free?",
		answer:
			"Yes. SurfSense and every update are free, with no account and no usage cap. You only pay a provider if you choose to connect a hosted model of your own.",
	},
	{
		question: "What kind of questions does it write?",
		answer:
			"Multiple-choice questions, each with four options, one right answer and an explanation of why it is right.",
	},
	{
		question: "Can I print the quiz?",
		answer:
			"The quiz is made to take in the app and has no download. For a printable test, ask Studio for a Word or PDF file with the questions and an answer key.",
	},
];

export default function QuizGeneratorPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "EducationalApplication")} />
			<BreadcrumbNav
				className="flex justify-center pt-8"
				items={[
					{ name: "Study guide maker", href: STUDY_GUIDE_URL },
					{ name: "Quiz generator", href: QUIZ_URL },
				]}
			/>

			<AudienceHero
				badge="Quiz generator"
				title="Generate a practice quiz from your"
				highlight="own material"
				lede="SurfSense writes a multiple-choice quiz from the sources you pick, with an explanation for every answer, a score, and Retake quiz for all the questions or only the ones you missed. It runs on your own laptop, it's free, and with the free local model nothing is sent anywhere."
				link={{ label: "Make a full study guide", href: STUDY_GUIDE_URL }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to make a quiz with SurfSense"
				steps={[
					{
						title: "Add your material",
						body: "Add readings, slides, handouts or notes to Sources, and wait until they're ready.",
					},
					{
						title: "Tick the chapter",
						body: "Tick the sources the quiz should cover. Studio uses the same ticks as chat.",
					},
					{
						title: "Click Quiz",
						body: "In Studio, click Quiz, write a prompt if you like, such as “harder questions on chapter 3”, and click Generate.",
					},
					{
						title: "Take it, then retake the misses",
						body: "Open it from Artifacts and answer. Your answers are saved as you go, and Retake quiz brings back all the questions or only the ones you missed.",
					},
				]}
			/>

			<AudienceCards
				badge="From your own material"
				headline="A quiz on what you actually have to learn"
				cards={[
					{
						heading: "PDF to quiz, scans included",
						icon: File02Icon,
						body: "Readings, slides and handouts, scanned pages too, become questions on the key facts, definitions, figures and causes.",
					},
					{
						heading: "An explanation for every answer",
						icon: InformationCircleIcon,
						body: "Each question says why its answer is right, so a wrong answer still teaches you something.",
					},
					{
						heading: "Retake only what you missed",
						icon: Quiz02Icon,
						body: "Retake the whole quiz, or only the questions you got wrong, until there are none left.",
					},
					{
						heading: "For teachers: a test from the chapter you assigned",
						icon: TeacherIcon,
						body: "Make a quiz from the chapter you set, to try in the app. For a printable test, ask Studio for a Word or PDF file with an answer key.",
						link: { label: "More for teachers", href: TEACHERS_URL },
					},
				]}
			/>

			<AudienceQuestions heading="Questions about the quiz generator" questions={QUESTIONS} />
		</>
	);
}
