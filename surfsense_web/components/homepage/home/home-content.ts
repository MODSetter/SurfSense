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
 * `light: true` marks a logo drawn light (a white-on-transparent crest, or a
 * favicon on its own coloured disc). Those are inverted so they show on the
 * light ground; everything else is drawn dark and reads as-is.
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

/** The node in the air-gap diagram that each `ON_YOUR_MACHINE` claim annotates. */
export type AirGapNode = "index" | "model" | "outputs";

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
export const ON_YOUR_MACHINE: (Cell & { node: AirGapNode })[] = [
	{
		title: "Your index lives on your disk",
		body: "A file you own, not a row in someone else's database. With a local model, pull the network cable and it keeps answering questions about the sources you already added. That matters most for a case file or a client's ledger.",
		node: "index",
	},
	{
		title: "Your model, or your own key",
		body: "Use SurfSense with a local model, or paste a key for a provider you already pay for. The key stays on the machine that uses it.",
		node: "model",
	},
	{
		title: "Sources become deliverables",
		body: "Turn what you have indexed into a deck, a report, a briefing or a study guide, generated and stored in the same local database as everything else.",
		node: "outputs",
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
 * `key` matches that file's format keys exactly; `HomeFormats` places each
 * one by key.
 */
export type Format = { key: string; label: string; body: string };

export const FORMATS: Format[] = [
	{ key: "summary", label: "Markdown", body: "A short brief of everything you have indexed." },
	{
		key: "docx",
		label: "Word",
		body: "An editable write-up you can revise afterward.",
	},
	{ key: "pptx", label: "Slides", body: "An editable presentation deck." },
	{ key: "xlsx", label: "Spreadsheet", body: "Tables pulled out of your sources." },
	{ key: "html", label: "Web page", body: "A standalone HTML page." },
	{ key: "pdf", label: "PDF", body: "A print-ready export of the same content." },
	{ key: "mindmap", label: "Mind map", body: "Concepts laid out as a linked graph." },
	{ key: "flashcards", label: "Flashcards", body: "A front-and-back deck for review." },
	{
		key: "quiz",
		label: "Quiz",
		body: "Test yourself, with every answer explained.",
	},
	{
		key: "podcast",
		label: "Podcast",
		body: "Your sources talked through as an audio conversation.",
	},
	{ key: "image", label: "Image", body: "Turn an idea into a picture." },
	{ key: "infographic", label: "Infographic", body: "Key figures laid out as one visual." },
];

/** H2 #2, #3, #4 — the three arguments that run as a ruled row. */
export const PILLARS: (Cell & { action: Action })[] = [
	{
		title: "Self-hosted, no account required",
		body: "No sign-up, no email, no workspace invite. The only identity involved is your computer's own user.",
		action: { label: "How installation works", href: "/docs" },
	},
	{
		title: "Bring your own model",
		body: "NotebookLM gives you Gemini only. Here the model is a setting: a local Qwen or Gemma, or OpenAI, Anthropic and anything OpenAI-compatible.",
		action: { label: "Supported models", href: "/docs" },
	},
	{
		title: "Install and start: no Docker, no terminal",
		body: "A normal installer for Windows, macOS and Linux, with llama.cpp built in. Pick a model on first launch and it runs on your computer.",
		action: { label: "Download the installer", href: DOWNLOADS_URL },
	},
];

/**
 * H2 #5, #6, #7 — one row per claim, each held to a line and two points.
 *
 * The plugins row replaced *Open source, audit it yourself*; its heading keeps
 * "open source" so the brief's phrase still has an H2. Plugins are not out
 * yet, so the row says so, as `/plugins` does.
 */
export type FeaturePoint = { title: string; body: string };

export const FEATURES: {
	key: "artifacts" | "plugins" | "private";
	heading: string;
	body: string;
	points: [FeaturePoint, FeaturePoint];
	action: Action;
}[] = [
	{
		key: "artifacts",
		heading: "Artifacts: decks, reports, briefings, podcasts",
		body: "Every source can become more than an answer.",
		points: [
			{
				title: "Twelve formats",
				body: "Slides, reports, podcasts, quizzes and more from one set of sources.",
			},
			{
				title: "Made offline",
				body: "Generated and stored on your machine, with no per-minute fee.",
			},
		],
		// Not the deliverables page: the "For confidential work" band below links it.
		action: { label: "Download and try them", href: DOWNLOADS_URL },
	},
	{
		key: "plugins",
		heading: "Open source, extended by plugins",
		body: "Each plugin pulls public data from one platform into your notebook. Coming soon.",
		points: [
			{
				title: "More places to search",
				body: "Reddit, YouTube, Google Maps, Amazon and the open web come first.",
			},
			{
				title: "Open by pull request",
				body: "Every plugin is code in the public repo, checked like the rest of it.",
			},
		],
		action: { label: "See the plugins", href: "/plugins" },
	},
	{
		key: "private",
		heading: "Private by construction",
		body: "Privacy as a structure, not a policy that can change.",
		points: [
			{
				title: "Nothing to hand over",
				body: "Data that never left your machine cannot be subpoenaed, breached or repriced.",
			},
			{
				title: "No account, ever",
				body: "Your index lives in your user folder. Delete the folder and it is gone.",
			},
		],
		action: { label: "Read the compliance notes", href: "/privacy" },
	},
];

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
	heading: "Private AI for business, with no vendor holding a copy",
	body: "Lawyers, accountants, consultants and engineers all have files they are not allowed to upload. SurfSense turns them into a deck, a report or a briefing anyway. The deliverable is built on the same machine the source sits on, so no vendor ever holds a copy of the contract, the ledger or the inspection report.",
	action: { label: "Learn more", href: BUSINESS_URL },
};

/** How a cell reads at a glance; the text beside it carries the nuance. */
export type CompareVerdict = "yes" | "no" | "partial";

export type CompareCell = { text: string; verdict: CompareVerdict };

export type CompareProduct = "ours" | "notebooklm" | "anythingllm" | "openNotebook";

export const COMPARE_PRODUCTS: { key: CompareProduct; name: string }[] = [
	{ key: "ours", name: "SurfSense" },
	{ key: "notebooklm", name: "NotebookLM" },
	{ key: "anythingllm", name: "AnythingLLM" },
	{ key: "openNotebook", name: "Open Notebook" },
];

export type CompareRow = { label: string } & Record<CompareProduct, CompareCell>;

/** Compared at the thing the brief says this page converts on: getting started
 * without an account, a cloud, or a container runtime. Verdicts are judged the
 * same way for every column; SurfSense does not win every row. */
export const COMPARE_ROWS: CompareRow[] = [
	{
		label: "Runs offline",
		ours: { text: "Yes, fully", verdict: "yes" },
		notebooklm: { text: "No, cloud only", verdict: "no" },
		anythingllm: { text: "Yes", verdict: "yes" },
		openNotebook: { text: "Yes", verdict: "yes" },
	},
	{
		label: "Account required",
		ours: { text: "None", verdict: "yes" },
		notebooklm: { text: "Google account", verdict: "no" },
		anythingllm: { text: "None", verdict: "yes" },
		openNotebook: { text: "None", verdict: "yes" },
	},
	{
		label: "Setup",
		ours: { text: "Desktop installer", verdict: "yes" },
		notebooklm: { text: "Web sign-in", verdict: "partial" },
		anythingllm: { text: "Installer or Docker", verdict: "yes" },
		openNotebook: { text: "Docker", verdict: "no" },
	},
	{
		label: "Choice of model",
		ours: { text: "Any, local or hosted", verdict: "yes" },
		notebooklm: { text: "Gemini only", verdict: "no" },
		anythingllm: { text: "Any", verdict: "yes" },
		openNotebook: { text: "Any", verdict: "yes" },
	},
	{
		label: "Model bundled",
		ours: { text: "Picked at first launch", verdict: "partial" },
		notebooklm: { text: "Not applicable", verdict: "partial" },
		anythingllm: { text: "Yes", verdict: "yes" },
		openNotebook: { text: "No", verdict: "no" },
	},
	{
		label: "Source code",
		ours: { text: "Open, auditable", verdict: "yes" },
		notebooklm: { text: "Closed", verdict: "no" },
		anythingllm: { text: "Open", verdict: "yes" },
		openNotebook: { text: "Open", verdict: "yes" },
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
			"Yes. SurfSense installs with llama.cpp built in, and its one-time setup screen has you pick a small language model that runs on the CPU. Once that one download finishes, you can add documents and ask questions with no network connection. An internet connection is only needed for that initial model download, if you choose a hosted model such as GPT or Claude, or when you download an update.",
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
