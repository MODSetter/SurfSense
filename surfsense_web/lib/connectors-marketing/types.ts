import type { ComponentType } from "react";

/** One extractable data point, rendered in the "What you can extract" grid. */
export interface ExtractField {
	label: string;
	description: string;
}

/** An outcome-framed use case, rendered as an H3 under the use-cases H2. */
export interface UseCase {
	title: string;
	description: string;
}

/** A single row in the "official API vs SurfSense" comparison table. */
export interface ComparisonRow {
	feature: string;
	/** The incumbent / DIY column value. */
	official: string;
	/** The SurfSense column value. */
	surfsense: string;
}

/** A FAQ entry. Answers are written to 40-60 words for featured-snippet fit. */
export interface FaqItem {
	question: string;
	answer: string;
}

/** One structured result row revealed in the agent-transcript hero artifact. */
export interface TranscriptRow {
	primary: string;
	secondary: string;
	/** Optional short tag rendered as a pill (e.g. "no website", "+92%"). */
	tag?: string;
}

/** The signature hero artifact: a realistic agent task and its structured output. */
export interface AgentTranscript {
	/** Natural-language task the agent is asked to perform. */
	prompt: string;
	/** The tool invocation the agent makes, mirroring the real capability surface. */
	toolCall: string;
	rows: TranscriptRow[];
	/** One-line summary shown under the rows (e.g. "100 places · 23 without a website"). */
	resultSummary: string;
}

/** A cross-link (to another connector, the homepage, or docs). */
export interface RelatedLink {
	label: string;
	href: string;
}

/**
 * The real capability surface for the API/MCP code samples. Values map 1:1 to
 * the backend `ScrapeInput`/`CommentsInput` contracts so examples are truthful.
 */
export interface ApiSample {
	/** Platform segment of the REST path, e.g. "google_maps". */
	platform: string;
	/** Verb segment of the REST path, e.g. "scrape". */
	verb: string;
	/** MCP tool name, e.g. "google_maps.scrape". */
	mcpTool: string;
	/** Request body keys/values, serialized into the cURL and Python samples. */
	requestBody: Record<string, unknown>;
}

/** One request parameter or response field in the schema reference tables. */
export interface SchemaField {
	name: string;
	/** Short type label, e.g. "string[]", "integer", "boolean", "object[]". */
	type: string;
	/** Rendered as a "required" pill next to the type. */
	required?: boolean;
	/** Default value shown for optional request parameters, e.g. '"new"', "10". */
	defaultValue?: string;
	description: string;
}

/**
 * The request/response contract rendered as the "API schema" section. Fields
 * map 1:1 to the backend capability `ScrapeInput`/`ScrapeOutput` models so the
 * reference is truthful.
 */
export interface ApiSchema {
	/** One-liner above the request table (e.g. which sources are required). */
	requestNote: string;
	request: SchemaField[];
	/** One-liner above the response table (envelope shape + billable unit). */
	responseNote: string;
	response: SchemaField[];
}

/** Everything needed to render one connector marketing page. */
export interface ConnectorPageContent {
	slug: string;
	/** Platform display name, e.g. "Reddit". */
	name: string;
	/** Clean product label for cards and headings. Defaults to `${name} API`. */
	cardTitle?: string;
	icon: ComponentType<{ className?: string }>;
	// SEO
	/** <= 60 chars, primary keyword front-loaded. */
	metaTitle: string;
	/** 150-160 chars, ends with a CTA. */
	metaDescription: string;
	keywords: string[];
	// Hero
	h1: string;
	/** Direct-answer paragraph placed in the first 150 words, keyword-rich. */
	heroLede: string;
	transcript: AgentTranscript;
	// Body
	extractIntro: string;
	extractFields: ExtractField[];
	useCasesHeading: string;
	useCases: UseCase[];
	comparison: {
		heading: string;
		intro: string;
		/** Label for the incumbent column, e.g. "Official Reddit API". */
		columnLabel: string;
		rows: ComparisonRow[];
	};
	api: ApiSample;
	schema: ApiSchema;
	faq: FaqItem[];
	related: RelatedLink[];
}
