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

/** Pinned release tag. The brief requires a pinned tag above the fold: the
 * shared `desktop-download-utils` resolves `/releases/latest`, which currently
 * serves a legacy build. */
export const PINNED_RELEASE_TAG = "v0.0.40";
export const DOWNLOADS_URL = "/downloads";
export const REPO_URL = "https://github.com/MODSetter/SurfSense";
export const RELEASE_URL = `${REPO_URL}/releases/tag/${PINNED_RELEASE_TAG}`;

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

export type Action = {
	label: string;
	href: string;
	external?: boolean;
};

/** H2 #1 — the offline / local / air-gapped claim, stated concretely. */
export const ON_YOUR_MACHINE: Cell[] = [
	{
		title: "The index lives on disk",
		body: "Your documents are parsed, embedded and stored in a database inside your own user directory. There is no upload step because there is nowhere to upload to.",
	},
	{
		title: "Nothing is sent anywhere",
		body: "No telemetry, no analytics, no sync service. Pull the network cable and the app keeps answering questions about the sources you have already added.",
	},
	{
		title: "Your keys, your provider",
		body: "Point it at a local model through Ollama, or paste a key for a provider you already pay for. The key stays on the machine that uses it.",
	},
	{
		title: "It is still yours offline",
		body: "Files stay in the formats you gave it. Nothing is locked behind an account, a subscription check, or a server that has to be reachable.",
	},
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
		title: "Install and go — no Docker, no terminal, no GPU",
		body: "A normal desktop installer for Windows, macOS and Linux. No compose file, no environment variables, no CUDA. The bundled small model runs on a laptop CPU.",
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
	key: "podcasts" | "open" | "private";
	heading: string;
	body: string[];
	action: Action;
}[] = [
	{
		key: "podcasts",
		heading: "Turn sources into podcasts, offline",
		body: [
			"Hand it a folder of papers and get back a two-voice conversation you can listen to on a commute. The script is written by the model you chose and the audio is synthesised on your machine, so a private document stays private even when it becomes a recording.",
			"The same sources also become summaries, study guides, flashcards and mind maps without a second pass over your data.",
		],
		action: { label: "How the podcast generator works", href: "/mcp-server" },
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
			"Most tools promise privacy as a policy — a commitment about what a company will choose not to do with data it nonetheless holds. A policy can change, and it can be compelled.",
			"Data that never left your machine cannot be handed over, subpoenaed, breached at a vendor, or repriced. That is a structural guarantee rather than a promise, and it is the only kind that survives a change of owner.",
		],
		action: { label: "Read the compliance notes", href: "/privacy" },
	},
];

export const PROOF_POINTS: Record<(typeof STORIES)[number]["key"], string[]> = {
	podcasts: [
		"Two-voice conversational scripts",
		"Speech synthesised locally",
		"Summaries and study guides",
		"Flashcards and mind maps",
		"Export as plain audio files",
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
		ours: "Yes, 0.5 GB",
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
			"Yes. SurfSense bundles a small language model that runs on the CPU, so once it is installed you can add documents and ask questions with no network connection. An internet connection is only needed if you choose a hosted model such as GPT or Claude, or when you download an update.",
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
			"NotebookLM has a free tier with usage limits and requires a Google account. SurfSense is free and open source with no account, no quota and no trial: you download it, install it, and use the bundled model at no cost. You only pay a provider if you choose to connect a hosted model of your own.",
	},
];
