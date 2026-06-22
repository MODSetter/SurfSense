import type { ArtifactKind, ArtifactStatus } from "../model/artifact";

function firstString(...values: unknown[]): string | null {
	for (const value of values) {
		if (typeof value === "string" && value.trim().length > 0) return value;
	}
	return null;
}

function numericId(value: unknown): number | null {
	return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Extracts entity id, title, and status for a single deliverable tool call. */
function describeArtifact(
	kind: ArtifactKind,
	args: Record<string, unknown>,
	result: Record<string, unknown>,
	hasResult: boolean
): { title: string; entityId: number | null; status: ArtifactStatus } {
	const resultStatus = typeof result.status === "string" ? result.status : null;
	const failed = resultStatus === "failed" || resultStatus === "error" || !!result.error;

	switch (kind) {
		case "report": {
			const entityId = numericId(result.report_id);
			return {
				title: firstString(result.title, args.topic) ?? "Report",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "resume": {
			const entityId = numericId(result.report_id);
			return {
				title: firstString(result.title) ?? "Resume",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "podcast": {
			const entityId = numericId(result.podcast_id);
			return {
				title: firstString(result.title, args.podcast_title) ?? "Podcast",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "video": {
			const entityId = numericId(result.video_presentation_id);
			return {
				title: firstString(result.title, args.video_title) ?? "Presentation",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "image": {
			const ready = typeof result.src === "string" && result.src.length > 0;
			return {
				title: firstString(result.title, args.prompt) ?? "Image",
				entityId: null,
				status: failed ? "error" : ready ? "ready" : hasResult ? "ready" : "running",
			};
		}
	}
}
