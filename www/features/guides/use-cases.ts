/**
 * The use-case videos the homepage and the For pages show: a guide's video beside its
 * steps cut down to three, so a visitor sees the work done before they download. The full
 * guide is a click away.
 *
 * Each entry is a guide in `content/docs/v2/guides/`. `heading` is that guide's title and
 * `title` its video's, so a renamed guide fails `use-cases.test.ts` until this follows.
 * Steps quote the app's labels as the guides do, with the docs' prose rules: no em dashes,
 * en dashes or spaced hyphens.
 */

export type UseCase = {
	/** The guide whose video and poster this shows, at /docs/v2/guides/<slug>. */
	slug: string;
	/** The tab that picks it. */
	label: string;
	/** The guide's title, over the steps. */
	heading: string;
	/** What the video shows, for screen readers. */
	title: string;
	steps: readonly [string, string, string];
};

const USE_CASES = {
	"ask-and-cite": {
		label: "Ask your files",
		heading: "Ask a question and check its citations",
		title: "Asking a question and opening the passage behind a citation",
		steps: [
			"Add PDFs, Word files or scans to Sources, click New chat and choose Basic (Q&A).",
			"Ask in plain words. Each point in the answer carries a numbered citation.",
			"Click a citation to open the passage behind it, highlighted, beside the answer.",
		],
	},
	"studio-documents": {
		label: "Make a document",
		heading: "Make a Word document, deck or PDF in Studio",
		title: "Making a Word document in Studio and opening it",
		steps: [
			"In Studio, click Word, Slides, Spreadsheet or PDF.",
			"Say what you want under Prompt (optional), and click Generate.",
			"Open it, and Download saves a real Office file you can edit.",
		],
	},
	"agent-documents": {
		label: "Write a report",
		heading: "Have the agent write a report or a deck",
		title: "The agent writing a Word report from the sources, then changing it",
		steps: [
			"Click New chat, and choose Agentic under Mode for this chat.",
			"Ask for the file you want, such as “a two-page Word report”.",
			"Open it in Studio, or ask in the same chat for a change.",
		],
	},
	"analyse-a-spreadsheet": {
		label: "Analyse a spreadsheet",
		heading: "Analyse a spreadsheet and chart it",
		title: "The agent answering a question about a CSV, then charting it in a Word document",
		steps: [
			"Add a spreadsheet or CSV to Sources.",
			"In an Agentic chat, ask about its numbers. The answer comes from an analysis.",
			"Ask for a chart in a Word document, drawn from the same numbers.",
		],
	},
	"study-materials": {
		label: "Flashcards and quizzes",
		heading: "Make flashcards, a quiz and a mind map",
		title: "Making flashcards, a quiz and a mind map, then using each one",
		steps: [
			"In Studio, click Flashcards, Quiz or Mind map, and click Generate.",
			"Turn each card with See answer, and mark it Got it or Needs review.",
			"Take the quiz: it marks each answer and gives your score at the end.",
		],
	},
	podcast: {
		label: "Make a podcast",
		heading: "Turn your sources into a podcast",
		title: "Briefing, making and playing a short podcast episode",
		steps: [
			"In Studio, click Podcast, and pick a style, a length and the speakers.",
			"Click Generate. SurfSense writes the script and voices each line.",
			"Play the episode with its transcript, or Download it as an MP3.",
		],
	},
	"transcribe-a-recording": {
		label: "Transcribe a recording",
		heading: "Turn a recording into a source",
		title: "Downloading a speech model, transcribing a recording, and citing it",
		steps: [
			"In Settings, open Speech recognition, click Add model and Download one.",
			"Add the recording to Sources like any other file.",
			"Ask about it. Each citation starts with the time it was said.",
		],
	},
	"contract-redline": {
		label: "Redline a contract",
		heading: "Redline a contract against your playbook",
		title:
			"Running the contract redline job on an NDA, then reading its tracked changes and comments in Studio",
		steps: [
			"Add the contract, as a .docx file, and your playbook to Sources.",
			"In Jobs, click Run beside Contract redline, pick both, and click Start.",
			"Click Open in Studio to check each tracked change and the comment on it.",
		],
	},
	"security-questionnaire": {
		label: "Answer a questionnaire",
		heading: "Fill in a security questionnaire from your policies",
		title:
			"Running the security questionnaire job on a workbook, then opening the filled-in copy in Studio",
		steps: [
			"Add the questionnaire, as an .xlsx file, and your policies to Sources.",
			"In Jobs, click Run beside Security questionnaire, tick your policies, and click Start.",
			"Click Open in Studio. Each answer has a comment naming the passage it rests on.",
		],
	},
	"privacy-network": {
		label: "Control what's sent",
		heading: "See and control what leaves your computer",
		title:
			"Unticking a site in Settings › Network, then the question SurfSense asks before it reaches that site",
		steps: [
			"Open Settings, then Network, to see every destination SurfSense knows.",
			"Untick one to block it: the next call is refused before it leaves your computer.",
			"When something needs a blocked one, SurfSense asks first: Allow or Cancel.",
		],
	},
} as const satisfies Record<string, Omit<UseCase, "slug">>;

export type UseCaseSlug = keyof typeof USE_CASES;

export const USE_CASE_SLUGS = Object.keys(USE_CASES) as UseCaseSlug[];

export function findUseCase(slug: UseCaseSlug): UseCase {
	return { slug, ...USE_CASES[slug] };
}
