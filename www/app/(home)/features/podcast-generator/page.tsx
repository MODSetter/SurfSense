import { JsonLd } from "@/components/site/json-ld";
import { PODCAST_URL, STUDY_GUIDE_URL } from "@/components/site/site-content";
import { Briefcase01Icon, Notebook01Icon, PodcastIcon, WifiOffIcon } from "@/components/ui/icons";
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
 * The podcast generator. Brief: `plans/community-local/seo/02-page-briefs.md`, "Podcast",
 * with the title's dash taken out as every string on this site is.
 *
 * The differentiator is that the voices are made on the user's computer, with the voice
 * model SurfSense ships, so there is no cloud text-to-speech and no per-minute cost. It
 * leads with the briefing use, the most common podcast request, and keeps study second.
 * The brief's options and the voice models come from the user guide (`content/docs/v2/`
 * `studio.mdx` and `voice.mdx`).
 */

const PAGE: AudiencePageMeta = {
	path: PODCAST_URL,
	title: "Offline AI Podcast Generator From Your Documents | SurfSense",
	description:
		"Turn reports, notes and readings into a podcast, voiced on your own computer with the voice model SurfSense ships. Free, with no account.",
	keywords: [
		"ai podcast generator",
		"notebooklm podcast",
		"turn notes into podcast",
		"notes to podcast",
		"notebooklm audio overview",
		"ai podcast from notes",
	],
	imageAlt: "SurfSense podcast generator",
};

export const metadata = audiencePageMetadata(PAGE);

const QUESTIONS: AudienceQuestion[] = [
	{
		question: "Is the podcast generator free?",
		answer:
			"Yes, with the voice model SurfSense ships, which runs on your computer. A voice model from a server is billed by its provider, and the podcast brief says so.",
	},
	{
		question: "Does it work offline?",
		answer:
			"Yes, with a local chat model and the voice model SurfSense ships. Kokoro 82M comes with the app and is chosen for you, so podcasts work offline from the start.",
	},
	{
		question: "What languages can it speak?",
		answer:
			"You choose the episode's language in the podcast brief. Each voice model lists its voices and languages in Settings › Audio.",
	},
	{
		question: "Can I download the episode?",
		answer: "Yes. Download saves the episode as an MP3 file.",
	},
];

export default function PodcastGeneratorPage() {
	return (
		<>
			<JsonLd data={audiencePageSchema(PAGE, undefined, "MultimediaApplication")} />

			<AudienceHero
				badge="Podcast generator"
				title="Turn your sources into a"
				highlight="podcast"
				lede="SurfSense turns the sources you pick into a podcast episode with its transcript. It is voiced on your own computer with Kokoro, the voice model SurfSense ships, so there is no cloud text-to-speech and no per-minute cost. It's free, with no account."
				link={{ label: "Make a study guide too", href: STUDY_GUIDE_URL }}
			/>

			<AudienceSteps
				badge="How it works"
				heading="How to make a podcast with SurfSense"
				video="podcast"
				steps={[
					{
						title: "Add your sources",
						body: "Add a report, a policy, readings or notes to Sources, and tick the ones the episode should cover.",
					},
					{
						title: "Open the podcast brief",
						body: "In Studio, click Podcast. The brief opens before anything is made.",
					},
					{
						title: "Choose the style, length and speakers",
						body: "Conversational, Debate, Interview, Monologue or Narrative; Short, Standard or Long; a voice for each speaker, and the episode's language.",
					},
					{
						title: "Generate and listen",
						body: "Click Generate. The episode appears in the Artifacts list, and Download saves it as an MP3.",
					},
				]}
			/>

			<AudienceCards
				badge="What it's for"
				headline="Audio from your own documents"
				cards={[
					{
						heading: "Turn a report into a briefing your team will actually listen to",
						icon: Briefcase01Icon,
						body: "A board paper, a policy or a research report becomes a short episode for the commute: pick Interview or Conversational, and Short, about 3 minutes.",
					},
					{
						heading: "NotebookLM Audio Overview, offline",
						icon: WifiOffIcon,
						body: "Like NotebookLM's Audio Overviews, the podcast talks your sources through. Here it is made on your own computer, with no Google account and nothing uploaded with a local model.",
					},
					{
						heading: "Revision you can listen to",
						icon: Notebook01Icon,
						body: "Turn a chapter into an episode for the way to class, then test yourself with flashcards and a quiz from the same sources.",
						link: { label: "Study guide maker", href: STUDY_GUIDE_URL },
					},
					{
						heading: "Five styles, three lengths, your choice of voices",
						icon: PodcastIcon,
						body: "Short is about 3 minutes, Standard about 8 and Long about 15. Each speaker has a role, such as Host, Expert or Narrator, and a voice of its own.",
					},
				]}
			/>

			<AudienceNotes heading="Voices on your computer, or from a server">
				<p>
					SurfSense ships Kokoro 82M and chooses it for you, so podcasts work offline from the
					start. Supertonic 3 and KittenTTS Mini 0.8 are other voice models you can download in
					Settings › Audio, and each lists its voices and languages.
				</p>
				<p>
					You can also use a voice model from an API connection that offers OpenAI-style speech.
					That provider bills each line, and the podcast brief says so.
				</p>
			</AudienceNotes>

			<AudienceQuestions heading="Questions about the podcast generator" questions={QUESTIONS} />
		</>
	);
}
