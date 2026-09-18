/**
 * The `/free` model catalog.
 *
 * Static. This was the hosted anonymous-chat model list, read from
 * `/api/v1/public/anon-chat/models` on every render. The hosted free chat is
 * closed, so there is no live endpoint left to read and no per-model service
 * behind these rows.
 *
 * What the rows do now is answer the question the visitor arrived with — "is
 * <model> on here?" — and hand them to the desktop app, which is what
 * `/free/[model_slug]` is for. So the list is picked on search demand instead
 * of on whatever the old service happened to have running.
 *
 * `term` and `volume` are the US monthly Google Ads figures behind each pick
 * (DataForSEO, pulled September 2026). They live in the row so the list can be
 * re-cut later without re-running the research, and so a model that has gone
 * stale can be spotted and swapped. Terms that returned no measurable volume
 * at the time of the pull were left out rather than guessed at: `gemini 3 pro`,
 * `grok 4`, `claude sonnet 4.5`, `claude opus 4.5`, `gpt 5.1`, `deepseek v4`,
 * `kimi k2` and `qwen 3 max` all came back with no data.
 *
 * `access` is the answer to "so how do I run this in the app?", and it is the
 * one claim on these pages that has to survive contact with the product. The
 * desktop app talks to any OpenAI-compatible endpoint with a key you supply
 * (`surfsense_local/backend/modules/llm/schemas.py`), and ships exactly one
 * family in its own catalog for offline use — Qwen3, via Ollama
 * (`surfsense_local/backend/modules/llm/recommendations/curated-models.json`).
 * No row says a model runs offline unless the app can actually do that today.
 */

export type FreeModelAccess = "offline" | "key";

export interface FreeModel {
	/** The row label, and the name the `/free/<slug>` page is written around. */
	name: string;
	provider: string;
	slug: string;
	access: FreeModelAccess;
	/** The keyword this row is here for, and its US monthly search volume. */
	term: string;
	volume: number;
}

/** Ordered by the volume behind each pick, so the rows a visitor scans first
 *  are the ones most of them came for. */
export const FREE_MODELS: FreeModel[] = [
	{
		name: "Gemini 3",
		provider: "Google",
		slug: "gemini-3-no-login",
		access: "key",
		term: "gemini 3",
		volume: 301000,
	},
	{
		name: "DeepSeek R1",
		provider: "DeepSeek",
		slug: "deepseek-r1-no-login",
		access: "key",
		term: "deepseek ai",
		volume: 49500,
	},
	{
		name: "Kimi",
		provider: "Moonshot AI",
		slug: "kimi-no-login",
		access: "key",
		term: "kimi ai",
		volume: 40500,
	},
	{
		name: "Qwen3",
		provider: "Alibaba",
		slug: "qwen3-no-login",
		// The one family the desktop app's local catalog ships.
		access: "offline",
		term: "qwen ai",
		volume: 33100,
	},
	{
		name: "Claude Sonnet",
		provider: "Anthropic",
		slug: "claude-sonnet-no-login",
		access: "key",
		term: "claude ai free",
		volume: 14800,
	},
	{
		name: "Gemini 2.5 Pro",
		provider: "Google",
		slug: "gemini-2-5-pro-no-login",
		access: "key",
		term: "gemini 2.5 pro",
		volume: 14800,
	},
	{
		name: "GLM 5",
		provider: "Z.ai",
		slug: "glm-5-no-login",
		access: "key",
		term: "glm 5",
		volume: 8100,
	},
	{
		name: "Grok",
		provider: "xAI",
		slug: "grok-no-login",
		access: "key",
		term: "grok ai free",
		volume: 6600,
	},
	{
		name: "GPT-4o",
		provider: "OpenAI",
		slug: "gpt-4o-no-login",
		access: "key",
		term: "gpt 4o",
		volume: 6600,
	},
	{
		name: "GPT-5 Mini",
		provider: "OpenAI",
		slug: "gpt-5-mini-no-login",
		access: "key",
		term: "gpt 5 mini",
		volume: 1900,
	},
	{
		name: "Llama 3.3",
		provider: "Meta",
		slug: "llama-3-3-no-login",
		access: "key",
		term: "llama ai free",
		volume: 90,
	},
	{
		name: "Mistral",
		provider: "Mistral AI",
		slug: "mistral-no-login",
		access: "key",
		term: "mistral free",
		volume: 50,
	},
];

/** What the catalog's last column says, and the phrase the model page reuses. */
export const ACCESS_LABEL: Record<FreeModelAccess, string> = {
	offline: "Runs offline",
	key: "Your own key",
};

/**
 * The shape of a slug this site could have published: alphanumerics, dots,
 * hyphens and underscores.
 *
 * This is a trust boundary, not decoration. Both the label below and the page's
 * canonical URL are built from whatever is in the URL, and both reach a JSON-LD
 * `<script>` block through `JSON.stringify` — a slug carrying `</script>` would
 * be an injection there. Next currently percent-encodes or rejects such a path
 * before it arrives, but that is the framework's behaviour rather than this
 * route's contract, so the route checks for itself.
 *
 * Deliberately permissive about case and separators and strict only about the
 * characters that matter: the closed service's slugs are not enumerable from
 * here, and rejecting a real one would 404 a page with live traffic.
 */
const PUBLISHED_SLUG = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/;

/** Whether a `/free/<slug>` path is shaped like one this site could have
 *  published. Anything else is not a URL worth answering — see the page. */
export function isPublishedSlug(slug: string): boolean {
	return PUBLISHED_SLUG.test(slug);
}

/** Initialisms, which would otherwise title-case to "Gpt" and "Glm". */
const INITIALISMS = new Set(["gpt", "glm", "ai", "llm", "oss", "qwq"]);

/**
 * A display name for any `/free/<slug>` URL.
 *
 * Catalog rows answer for themselves. Everything else is derived from the slug,
 * because the URLs the old hosted service put into Google are its own model
 * slugs — `gpt-5.4-mini-no-login` and friends — and those are the pages with
 * the traffic actually worth converting. They have to render a sensible page
 * rather than a 404, and neither the catalog nor this file knows the full list
 * the hosted service once served.
 */
export function freeModelLabel(slug: string): string {
	const known = FREE_MODELS.find((model) => model.slug === slug);
	if (known) {
		return known.name;
	}

	if (!isPublishedSlug(slug)) {
		return "This model";
	}

	const words = slug
		.replace(/-no-login$/, "")
		.split("-")
		.filter(Boolean)
		.map((token) =>
			INITIALISMS.has(token.toLowerCase())
				? token.toUpperCase()
				: token.charAt(0).toUpperCase() + token.slice(1)
		);

	return words.length > 0 ? words.join(" ") : "This model";
}
