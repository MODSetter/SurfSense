import Link from "next/link";
import { JsonLd } from "@/components/site/json-ld";
import { CONTRACT_REDLINE_URL, LAWYERS_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import {
	BubbleChatIcon,
	ClipboardCheckIcon,
	Key01Icon,
	LegalDocument01Icon,
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
	AudienceNotes,
	type AudienceQuestion,
	AudienceQuestions,
	AudienceSteps,
} from "@/features/audience-pages/audience-sections";

/**
 * The contract redline job. Brief: `plans/community-local/seo/09-audience-pages.md`,
 * `/jobs/contract-redline`. What the job does, and every label quoted here, comes from the
 * user guide's "Review a contract" (`content/docs/v2/jobs.mdx`), so the two never disagree.
 *
 * ADR 0086 holds public redline pages for a lawyer's review: record who read this page
 * before the release that ships it. No accuracy figure goes on it before the maintainer has checked the eval's stance file.
 */

const GUIDE_URL = "/docs/v2/guides/contract-redline";

const PAGE: AudiencePageMeta = {
	path: CONTRACT_REDLINE_URL,
	title: "AI Contract Review Against Your Own Playbook | SurfSense",
	description:
		"SurfSense reviews a Word contract against your firm's playbook and returns tracked changes and comments, on your own computer. Free and open source.",
	keywords: [
		"ai contract review",
		"contract review ai",
		"contract redlining software",
		"ai redlining",
		"ai legal document review",
		"nda review",
		"contract playbook",
	],
	imageAlt: "SurfSense contract redline",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "What does the contract redline need?",
		answer:
			"A contract as a Word file (.docx), your firm's playbook in Sources, and a chat model selected in Settings. It is free, like the rest of the app, with no licence. Save an older Word file (.doc) as .docx first.",
	},
	{
		question: "Does it make up positions?",
		answer:
			"No. It checks the contract only against your playbook. Where your playbook says nothing on a point, the contract is left as it is there.",
	},
	{
		question: "Can the other side see SurfSense's reasoning?",
		answer:
			"No. SurfSense's reasoning and the words of your playbook it rests on are internal comments, which stay in Studio: every download leaves them out. The other side sees the tracked changes and the comments written for them, and you can turn those comments off in the job's Settings.",
	},
	{
		question: "Which model should I use?",
		answer:
			"The job answers with the chat model selected in Settings. A model that runs on your computer keeps the contract on it, but it is usually smaller and leaves more points for a person to settle.",
	},
	{
		question: "Is my contract uploaded anywhere?",
		answer:
			"Running a job sends SurfSense nothing. The contract and your playbook are read on your computer, and go only to the model you chose, when that model doesn't run on your computer.",
	},
];

export default function ContractRedlinePage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE)} />

			<AudienceHero
				badge="Contract redline"
				title="AI contract review against your own playbook, as tracked changes in"
				highlight="Word"
				lede="Add a contract you received, as a Word file, and your firm's playbook. SurfSense checks the contract one review point at a time and marks up a copy with tracked changes and comments. It never makes up a position: where your playbook says nothing, the contract is left as it is."
				note="A job built into SurfSense, free for everyone, with no licence or account."
				link={{ label: "Read the guide", href: GUIDE_URL }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to review a contract with SurfSense"
				video="contract-redline"
				steps={[
					{
						title: "Add the contract and your playbook",
						body: "Add the contract, as a .docx file, and your playbook to Sources. Your playbook is your firm's written positions, its own standard agreement, or both.",
					},
					{
						title: "Run the contract redline",
						body: "In Jobs, choose Run beside Contract redline. Pick the contract under Contract to review, tick your playbook under Your firm’s playbook, and choose Start.",
					},
					{
						title: "Let it work through the points",
						body: "Jobs counts review points as it goes, then says how many were changed, how many meet your playbook, how many are not in it, and which need a person.",
					},
					{
						title: "Accept or reject each change",
						body: "The copy opens in Studio with tracked changes by SurfSense. Accept or reject them in Studio or in Word, and download the copy with With changes.",
					},
				]}
			/>

			<AudienceCards
				badge="What you get back"
				headline="A marked-up copy, with a reason for every change"
				cards={[
					{
						heading: "Tracked changes, only where they're needed",
						icon: LegalDocument01Icon,
						body: "Where a clause departs from your playbook, SurfSense rewrites it and marks only the words that change. A term your playbook asks for and the contract lacks is added as a new paragraph.",
					},
					{
						heading: "A comment the other side can read",
						icon: BubbleChatIcon,
						body: "Each change carries a comment giving its reason. In the job's Settings, turn off “Explain each change to the other side” and every comment SurfSense writes stays internal.",
					},
					{
						heading: "Internal comments that never leave Studio",
						icon: Key01Icon,
						body: "SurfSense's reasoning, with the words of your playbook it rests on, is an internal comment. Internal comments stay in Studio: every download leaves them out.",
					},
					{
						heading: "An outcome for every review point",
						icon: ClipboardCheckIcon,
						body: "Each point is changed, meets your playbook, is not in your playbook, or is left for a person, with an internal comment saying why. Your own file is never changed.",
					},
				]}
			/>

			<AudienceAnswer
				heading="SurfSense never receives your contract"
				points={[
					"Runs in the app on your computer",
					"Sends SurfSense nothing",
					"Never changes your own file",
					"Works with a local model or your firm's key",
				]}
			>
				<p>
					Running a job sends SurfSense nothing. The contract and your playbook are read on your
					computer, and go only to the model you chose for the job, when that model doesn't run on
					your computer.
				</p>
				<p>
					Each run makes a revised copy in Studio. Your own file is never changed, and earlier
					versions of the copy stay in Studio too.
				</p>
			</AudienceAnswer>

			<AudienceNotes heading="What it reviews today">
				<p>
					Its review points are those of a non-disclosure agreement, such as what counts as
					confidential, notice of a compelled disclosure, return or destruction, and survival. Each
					point is checked on its own against your playbook.
				</p>
				<p>
					SurfSense reviews and changes the body of the contract only, never its headers, footers or
					footnotes. A contract that already holds tracked changes is reviewed as it reads with
					them. A point SurfSense can't settle, or whose change it can't place in the contract, is
					left for a person.
				</p>
			</AudienceNotes>

			<AudienceClosing
				badge="Free"
				heading="Free in the app, for everyone"
				link={{ label: "Read the guide", href: GUIDE_URL }}
			>
				<p>
					The contract redline is built into SurfSense, with the security questionnaire, and is free
					like the rest of the app: no licence, no account and no card. Working on a legal team?{" "}
					<Link className={siteText.link} href={LAWYERS_URL}>
						See what else SurfSense does for lawyers
					</Link>
					.
				</p>
			</AudienceClosing>

			<AudienceQuestions heading="Questions about the contract redline" questions={QUESTIONS} />
		</>
	);
}
