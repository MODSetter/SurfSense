/**
 * Client-side, per-platform URL hints for the playground (UX only).
 *
 * The scraper API stays authoritative: it rejects malformed URLs (422), and
 * each platform decides what it can actually scrape. These hints only *warn*,
 * before a run, when a line in a platform's ``urls`` field is not a URL for
 * that platform — so a typo (wrong site, missing scheme) is caught without a
 * round-trip. They never block the run.
 */

interface PlatformUrlRule {
	/** Host suffixes (``youtube.com``) or ``.``-terminated prefixes (``amazon.``). */
	hosts: string[];
	/** Human platform name used in the warning message. */
	label: string;
}

/**
 * Keyed by platform slug. Instagram is intentionally absent: its ``urls`` field
 * also accepts bare ``@handles``, so a non-URL line there is not a mistake.
 */
const PLATFORM_URL_RULES: Record<string, PlatformUrlRule> = {
	amazon: { hosts: ["amazon.", "amzn.to", "a.co"], label: "Amazon" },
	walmart: { hosts: ["walmart.com"], label: "Walmart" },
	reddit: { hosts: ["reddit.com", "redd.it"], label: "Reddit" },
	youtube: { hosts: ["youtube.com", "youtu.be"], label: "YouTube" },
	tiktok: { hosts: ["tiktok.com"], label: "TikTok" },
	google_maps: { hosts: ["google.", "goo.gl"], label: "Google Maps" },
	indeed: { hosts: ["indeed.com"], label: "Indeed" },
};

/** The array fields that carry platform URLs at the capability layer. */
const URL_FIELD_NAMES = new Set(["urls", "video_urls", "startUrls"]);

function hostMatches(host: string, patterns: string[]): boolean {
	return patterns.some((pattern) =>
		pattern.endsWith(".")
			? host.includes(pattern)
			: host === pattern || host.endsWith(`.${pattern}`)
	);
}

function article(word: string): "a" | "an" {
	return /^[aeiou]/i.test(word) ? "an" : "a";
}

function isPlatformUrl(line: string, rule: PlatformUrlRule): boolean {
	try {
		const { protocol, hostname } = new URL(line);
		if (protocol !== "http:" && protocol !== "https:") return false;
		return hostMatches(hostname.toLowerCase(), rule.hosts);
	} catch {
		return false;
	}
}

/**
 * Warn if any line in a platform ``urls`` field is not a URL for that platform.
 * Returns ``undefined`` when the field/platform has no rule or every line is OK.
 */
export function urlFieldWarning(
	platform: string,
	fieldName: string,
	value: unknown
): string | undefined {
	const rule = PLATFORM_URL_RULES[platform];
	if (!rule || !URL_FIELD_NAMES.has(fieldName)) return undefined;

	const badLines = String(value ?? "")
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean)
		.filter((line) => !isPlatformUrl(line, rule));

	if (badLines.length === 0) return undefined;
	return `Not ${article(rule.label)} ${rule.label} URL: ${badLines.join(", ")}`;
}

/** Per-field warnings for the current form values (empty when every URL looks valid). */
export function urlFieldWarnings(
	platform: string,
	values: Record<string, unknown>
): Record<string, string> {
	const warnings: Record<string, string> = {};
	for (const [name, value] of Object.entries(values)) {
		const warning = urlFieldWarning(platform, name, value);
		if (warning) warnings[name] = warning;
	}
	return warnings;
}
