import { normalizeArtifactFormat } from "./artifact-format-catalog";

export type ArtifactRendererResolution =
	| { kind: "semantic"; key: string }
	| { kind: "mime"; key: string }
	| { kind: "markdown" }
	| { kind: "unviewable" };

export function resolveArtifactRenderer({
	format,
	primaryMimeType,
	hasPrimary,
	hasMarkdown,
	semanticFormats,
	mimeTypes,
}: {
	format: string | null | undefined;
	primaryMimeType: string | null | undefined;
	hasPrimary: boolean;
	hasMarkdown: boolean;
	semanticFormats: ReadonlySet<string>;
	mimeTypes: ReadonlySet<string>;
}): ArtifactRendererResolution {
	const normalizedFormat = normalizeArtifactFormat(format);
	if (semanticFormats.has(normalizedFormat)) {
		return { kind: "semantic", key: normalizedFormat };
	}
	if (hasPrimary) {
		return primaryMimeType && mimeTypes.has(primaryMimeType)
			? { kind: "mime", key: primaryMimeType }
			: { kind: "unviewable" };
	}
	return hasMarkdown ? { kind: "markdown" } : { kind: "unviewable" };
}
