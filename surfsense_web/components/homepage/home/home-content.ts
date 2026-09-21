import { BUSINESS_URL, DOWNLOADS_URL, REPO_URL } from "@/components/site/site-content";

/**
 * Homepage copy and data.
 *
 * The heading order here is not editorial — it is the SEO skeleton from
 * `plans/community-local/seo/02-page-briefs.md` (`/` landing, B6). Each H2
 * carries one demand phrase and the order is load-bearing. Change the wording
 * freely; do not reorder or drop a heading without re-reading that brief.
 *
 * Hoisted to module scope so the arrays are allocated once per process rather
 * than on every render.
 */

/**
 * Pinned release tag.
 *
 * Unreferenced since the hero's "grab v0.0.40 directly" line was removed, and
 * the tag it names is the retired legacy app. A download link added here should
 * take `APP_RELEASE_TAG` from `lib/app-release.ts`, which `bump-version.sh`
 * keeps current, rather than this constant. Delete both once that happens.
 */
export const PINNED_RELEASE_TAG = "v0.0.40";
export const RELEASE_URL = `${REPO_URL}/releases/tag/${PINNED_RELEASE_TAG}`;

export { BUSINESS_URL, DOWNLOADS_URL, REPO_URL };

/**
 * Real self-serve signups pulled from prod, curated to the most recognisable
 * names.
 *
 * These are individual users, not signed enterprise accounts. The label reads
 * "Trusted by experts at", which says the people are at these organisations —
 * keep it phrased that way. A heading that reads as the organisation itself
 * endorsing the product ("Trusted by", with the logos as the subject) would be
 * a claim the signup data does not support.
 *
 * Logos live in `public/logos/`.
 */
/**
 * `light: true` marks a logo that must not be inverted: a white-on-transparent
 * crest, or a favicon drawn on its own coloured disc. Everything else is
 * inverted.
 *
 * Inverting is the default because most of these third-party SVGs draw in a
 * single dark colour, and several have paths with no `fill` at all, which the
 * renderer defaults to black; unfiltered they would be invisible here. The
 * alternative, a blanket `brightness(0) invert(1)`, does guarantee visibility
 * but fills every interior counter and reduces a detailed crest to a disc.
 */
export const COMPANIES: { title: string; file: string; light?: boolean }[] = [
	{ title: "UC Berkeley", file: "berkeley.svg", light: true },
	{ title: "USC", file: "usc.svg" },
	{ title: "Texas A&M", file: "tamu.svg" },
	{ title: "UW\u2013Madison", file: "wisc.svg", light: true },
	{ title: "Pitt", file: "pitt.svg", light: true },
	{ title: "Korean Air", file: "koreanair.svg" },
	{ title: "Iron Mountain", file: "ironmountain.svg" },
	{ title: "Globant", file: "globant.svg" },
	{ title: "Devoteam", file: "devoteam.svg" },
	{ title: "VNG", file: "vng.svg" },
	{ title: "TPBank", file: "tpbank.svg" },
	{ title: "OpenGov", file: "opengov.svg" },
	{ title: "WeLab", file: "welab.svg" },
	{ title: "Leverage Edu", file: "leverage-edu.svg", light: false },
	{ title: "Zopper", file: "zopper.svg" },
	{ title: "Tec de Monterrey", file: "tec.svg", light: true },
	{ title: "Chulalongkorn", file: "chula.svg", light: true },
	{ title: "Univ. of Bristol", file: "bristol.svg", light: true },
	{ title: "Nutresa", file: "nutresa.svg" },
	{ title: "Bosta", file: "bosta.svg" },
];

export type Cell = {
	title: string;
	body: string;
};

/** Which bento cells in `ON_YOUR_MACHINE` carry a designed SVG illustration. */
export type IllustratedCell = "no-cloud" | "local-key" | "artifacts";

export type Action = {
	label: string;
	href: string;
	external?: boolean;
};

/**
 * H2 #1 — the offline / local / air-gapped claim, stated concretely.
 *
 * The first cell says *who* that protects, not only that it is true: the
 * 17 Sep 2026 production-chat pass found professional work outruns study by
 * about 1.8 to 1 among users who state a task, so the reader of this claim is
 * more often someone handling a client's material than a student
 * (`plans/community-local/seo/07-what-users-do.md`).
 */
export const ON_YOUR_MACHINE: (Cell & { illustration?: IllustratedCell })[] = [
	{
		title: "No cloud in the loop",
		body: "The index is a file on your disk, not a row in someone else's database. Pull the network cable and it keeps answering questions about the sources you already added. That matters most when the source is a case file or a client's ledger.",
		illustration: "no-cloud",
	},
	{
		title: "Local model or your own key",
		body: "Use SurfSense with a local model, or paste a key for a provider you already pay for. The key stays on the machine that uses it.",
		illustration: "local-key",
	},
	{
		title: "Sources become deliverables",
		body: "Turn what you have indexed into a deck, a report, a briefing or a study guide, generated and stored in the same local database as everything else.",
		illustration: "artifacts",
	},
];

/**
 * Not one of the brief's seven H2s — a new band below the claims tabs, so its
 * own headline is a `<p>` styled like an H2, the same convention `HomePillars`
 * and `HomeCompare` use to add a section without disturbing the SEO skeleton's
 * heading count.
 *
 * The twelve formats and their order come straight from the backend's own
 * catalog (`surfsense_local/backend/modules/artifacts/formats.py`), and each
 * `key` matches that file's format keys exactly — `HomeFormats` looks up an
 * icon per key from the same set the in-app Studio library uses
 * (`features/artifacts/lib/artifact-format-catalog.ts`), so the homepage and
 * the product never draw a format with two different icons.
 */
export type Format = { key: string; label: string; body: string };

export const FORMATS: Format[] = [
	{ key: "summary", label: "Summary", body: "A short brief of everything you have indexed." },
	{
		key: "docx",
		label: "Document",
		body: "An editable write-up you can revise afterward.",
	},
	{ key: "pptx", label: "Slides", body: "An editable presentation deck." },
	{ key: "xlsx", label: "Spreadsheet", body: "Tables pulled out of your sources." },
	{ key: "html", label: "Web page", body: "A standalone page you can host anywhere." },
	{ key: "pdf", label: "PDF", body: "A print-ready export of the same content." },
	{ key: "mindmap", label: "Mind map", body: "Concepts laid out as a linked graph." },
	{ key: "flashcards", label: "Flashcards", body: "A front-and-back deck for review." },
	{ key: "quiz", label: "Quiz", body: "Multiple-choice questions with source citations." },
	{
		key: "podcast",
		label: "Podcast",
		body: "A two-voice audio conversation, synthesised offline.",
	},
	{ key: "image", label: "Image", body: "A generated illustration for a single idea." },
	{ key: "infographic", label: "Infographic", body: "Key figures laid out as one visual." },
];

/** H2 #2, #3, #4 — the three arguments that run as a ruled row. */
export const PILLARS: (Cell & { action: Action })[] = [
	{
		title: "Self-hosted, no account required",
		body: "There is no sign-up, no email, no workspace to be invited to. Install it and start; the only identity involved is your operating system user.",
		action: { label: "How installation works", href: "/docs" },
	},
	{
		title: "Bring your own model",
		body: "NotebookLM gives you Gemini and nothing else. Here the model is a setting: a local Qwen or Llama through Ollama, or OpenAI, Anthropic and anything OpenAI-compatible.",
		action: { label: "Supported models", href: "/docs" },
	},
	{
		title: "Install and go: no Docker, no terminal, no GPU",
		body: "A normal desktop installer for Windows, macOS and Linux. No compose file, no environment variables, no CUDA. Ollama ships in the box; pick a model on first launch and it runs on a laptop CPU.",
		action: { label: "Download the installer", href: DOWNLOADS_URL },
	},
];

/**
 * H2 #5, #6, #7 — each claim paired with the concrete things that back it.
 *
 * The proof points are deliberately short and checkable: the reference design
 * runs a claim alongside a ruled list, and a list of adjectives would waste
 * that structure.
 */
export const STORIES: {
	key: "artifacts" | "open" | "private";
	heading: string;
	body: string[];
	action: Action;
}[] = [
	{
		key: "artifacts",
		heading: "Artifacts: decks, reports, briefings, podcasts",
		body: [
			"Every source can become more than an answer: a slide deck, a written report, a two-voice briefing podcast or an infographic. The same builders make a study guide, a flashcard deck and a practice quiz when that is the job instead.",
			"Every format is generated and stored in the same local database as everything else. No cloud model in the loop, no per-minute fee, no second pass over your data to make them.",
		],
		// Not the deliverables page: the "For confidential work" band lower down
		// already links it, and two links to one page from one screen read as a
		// mistake. The twelve-format row sits directly below this tab, so the
		// useful next step here is the installer.
		action: { label: "Download and try them", href: DOWNLOADS_URL },
	},
	{
		key: "open",
		heading: "Open source, audit it yourself",
		body: [
			"Every claim on this page is checkable, because the code that would have to betray it is public. There is no minified bundle phoning home, no closed sync daemon, and no build you cannot reproduce.",
			"If you want to know what leaves your machine, read the network layer. That is a shorter file than you would expect.",
		],
		action: { label: "Read the source on GitHub", href: REPO_URL, external: true },
	},
	{
		key: "private",
		heading: "Private by construction",
		body: [
			"Most tools promise privacy as a policy: a commitment about what a company will choose not to do with data it nonetheless holds. A policy can change, and it can be compelled.",
			"Data that never left your machine cannot be handed over, subpoenaed, breached at a vendor, or repriced. That is a structural guarantee rather than a promise, and it is the only kind that survives a change of owner.",
		],
		action: { label: "Read the compliance notes", href: "/privacy" },
	},
];

export const PROOF_POINTS: Record<(typeof STORIES)[number]["key"], string[]> = {
	artifacts: [
		"Editable decks and reports",
		"Two-voice briefings, synthesised offline",
		"Infographics and one-page summaries",
		"Study guides and flashcard decks",
		"Practice quizzes with citations",
		"No per-minute generation fee",
	],
	open: [
		"Source public on GitHub",
		"Reproducible desktop builds",
		"No telemetry in the binary",
		"Auditable network layer",
		"Community issues and PRs",
		"Apache-licensed",
	],
	private: [
		"No account, ever",
		"Index stored in your user directory",
		"Model keys never leave the device",
		"Works with the network unplugged",
		"Nothing to subpoena from us",
		"Delete it by deleting a folder",
	],
};

/**
 * H2 #8 — *For confidential work*, added to the brief on 17 Sep 2026.
 *
 * A copy change, not a new front: the same privacy claim the page already
 * makes, addressed to someone spending company money. It names the professions
 * so the `ai for lawyers` / `ai for accountants` vocabulary is caught here
 * without ten vertical pages, and carries `private ai for business`, which went
 * 1,900 → 5,400 → 12,100 over three months.
 *
 * One paragraph and a link, deliberately — the argument is made in full on the
 * page it links to, and a second section here would compete with it.
 */
export const CONFIDENTIAL: { eyebrow: string; heading: string; body: string; action: Action } = {
	eyebrow: "For confidential work",
	heading: "Private AI for business, because the file never moves",
	body: "Lawyers, accountants, consultants and engineers all do the same job with this: a file they are not allowed to upload goes in, and a deck, a report or a briefing comes out. The deliverable is built on the same machine the source sits on, so no vendor ever holds a copy of the contract, the ledger or the inspection report.",
	action: { label: "Turn confidential documents into deliverables", href: BUSINESS_URL },
};

export type CompareRow = {
	label: string;
	ours: string;
	notebooklm: string;
	anythingllm: string;
	openNotebook: string;
};

/** Compared at the thing the brief says this page converts on: getting started
 * without an account, a cloud, or a container runtime. */
export const COMPARE_ROWS: CompareRow[] = [
	{
		label: "Runs offline",
		ours: "Yes, fully",
		notebooklm: "No, cloud only",
		anythingllm: "Yes",
		openNotebook: "Yes",
	},
	{
		label: "Account required",
		ours: "None",
		notebooklm: "Google account",
		anythingllm: "None",
		openNotebook: "None",
	},
	{
		label: "Setup",
		ours: "Desktop installer",
		notebooklm: "Web sign-in",
		anythingllm: "Installer or Docker",
		openNotebook: "Docker + env vars",
	},
	{
		label: "Choice of model",
		ours: "Any, local or hosted",
		notebooklm: "Gemini only",
		anythingllm: "Any",
		openNotebook: "Any",
	},
	{
		label: "Model bundled",
		ours: "No, pick one during setup",
		notebooklm: "Not applicable",
		anythingllm: "Yes",
		openNotebook: "No",
	},
	{
		label: "Source code",
		ours: "Open, auditable",
		notebooklm: "Closed",
		anythingllm: "Open",
		openNotebook: "Open",
	},
];

/** Answers are written as quotable definitions: one plain paragraph that an AI
 * Overview or a PAA box can lift verbatim. Questions come from the PAA boxes
 * catalogued in `plans/community-local/seo/05-serp-landscape.md`. */
export const HOME_FAQ = [
	{
		question: "Can I self-host an AI?",
		answer:
			"Yes. A self-hosted AI runs the model and stores its data on hardware you control rather than a provider's servers. SurfSense is a desktop application that does this without a server at all: it installs like any other app, keeps its index in your user directory, and can run a local model so that no request ever leaves the machine.",
	},
	{
		question: "Is there an AI I can use without internet?",
		answer:
			"Yes. SurfSense installs with Ollama built in, and its one-time setup screen has you pick a small language model that runs on the CPU. Once that one download finishes, you can add documents and ask questions with no network connection. An internet connection is only needed for that initial model download, if you choose a hosted model such as GPT or Claude, or when you download an update.",
	},
	{
		question: "Can I run NotebookLM locally?",
		answer:
			"No. NotebookLM is a Google cloud service: it requires a Google account, uploads your sources to Google's servers, and cannot be installed on your own machine. Running the same workflow locally means using an alternative built for it, such as SurfSense, which keeps sources and answers on your computer.",
	},
	{
		question: "Is there an open-source alternative to NotebookLM?",
		answer:
			"Yes. SurfSense is an open-source NotebookLM alternative: the source is public and auditable, it runs air-gapped on Windows, macOS and Linux, it works with any model you choose rather than Gemini alone, and it turns your sources into summaries, study guides and podcasts entirely offline.",
	},
	{
		question: "Is there a free version of NotebookLM?",
		answer:
			"NotebookLM has a free tier with usage limits and requires a Google account. SurfSense is free and open source with no account, no quota and no trial: you download it, install it, pick a local model in the one-time setup screen, and chat at no cost. You only pay a provider if you choose to connect a hosted model of your own.",
	},
];
