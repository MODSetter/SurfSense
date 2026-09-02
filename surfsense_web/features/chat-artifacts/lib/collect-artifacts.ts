import type { ThreadMessageLike } from "@assistant-ui/react";
import type { ArtifactListItem } from "@/features/artifacts/model/artifact";
import { ARTIFACT_TOOL_KINDS, type ArtifactToolKind, type ChatArtifact } from "../model/artifact";

interface ToolCallPart {
	type: "tool-call";
	toolCallId: string;
	toolName: string;
	args?: unknown;
	result?: unknown;
}

function isToolCallPart(part: unknown): part is ToolCallPart {
	return (
		typeof part === "object" &&
		part !== null &&
		(part as { type?: unknown }).type === "tool-call" &&
		typeof (part as { toolCallId?: unknown }).toolCallId === "string" &&
		typeof (part as { toolName?: unknown }).toolName === "string"
	);
}

function asRecord(value: unknown): Record<string, unknown> {
	return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function numericId(value: unknown): number | null {
	return typeof value === "number" && Number.isFinite(value) ? value : null;
}

type Described = {
	entityId: number | null;
	artifactId?: number;
	legacyEntityId?: number;
	failed: boolean;
};

export interface ArtifactCandidate {
	key: string;
	toolKind: ArtifactToolKind;
	toolCallId: string;
	entityId: number;
	artifactId?: number;
	legacyEntityId?: number;
	title: string;
	/** Missing only on pre-explicit-format save_artifact message results. */
	format?: string;
}

/** Extracts persistence identity and status for a single deliverable tool call. */
function describeArtifact(kind: ArtifactToolKind, result: Record<string, unknown>): Described {
	const resultStatus = typeof result.status === "string" ? result.status : null;
	const failed =
		resultStatus === "failed" ||
		resultStatus === "error" ||
		resultStatus === "cancelled" ||
		!!result.error;

	switch (kind) {
		case "file": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			return {
				entityId: artifactId ?? null,
				artifactId,
				failed: failed || resultStatus !== "saved",
			};
		}
		case "podcast": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			const legacyEntityId = numericId(result.podcast_id) ?? undefined;
			const entityId = artifactId ?? legacyEntityId ?? null;
			return {
				entityId,
				artifactId,
				legacyEntityId,
				failed,
			};
		}
		case "video": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			const legacyEntityId = numericId(result.video_presentation_id) ?? undefined;
			const entityId = artifactId ?? legacyEntityId ?? null;
			return {
				entityId,
				artifactId,
				legacyEntityId,
				failed,
			};
		}
		case "image": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			return {
				entityId: artifactId ?? null,
				artifactId,
				failed,
			};
		}
	}
}

function text(value: unknown): string | null {
	return typeof value === "string" && value.trim() ? value.trim() : null;
}

function extractMetadataWithLegacyFormatCompatibility(
	kind: ArtifactToolKind,
	args: Record<string, unknown>,
	result: Record<string, unknown>
): Pick<ArtifactCandidate, "title" | "format"> {
	switch (kind) {
		case "file": {
			return {
				title: text(result.title) ?? text(args.title) ?? "Artifact",
				// Compatibility layer: old saved tool results predate `format`.
				// Keep their identity for persisted-row resolution; never infer
				// semantic format from a filename.
				format: text(result.format) ?? undefined,
			};
		}
		case "podcast":
			return {
				title: text(result.title) ?? text(args.podcast_title) ?? "Podcast",
				format: "podcast",
			};
		case "video":
			return {
				title: text(result.title) ?? text(args.video_title) ?? "Video presentation",
				format: "video",
			};
		case "image":
			return {
				title: text(result.title) ?? text(result.alt) ?? text(args.prompt) ?? "Generated image",
				format: "image",
			};
	}
}

/**
 * Aggregate the deliverable artifacts referenced across a thread's messages.
 *
 * Scans assistant tool-call parts and keeps successful deliverable tool results
 * with an identity that can be reconciled to durable Artifact rows. In-flight
 * and failed calls remain visible only in the conversation.
 */
export function collectArtifacts(messages: readonly ThreadMessageLike[]): ArtifactCandidate[] {
	const byKey = new Map<string, ArtifactCandidate>();

	for (const message of messages) {
		if (message.role !== "assistant" || !Array.isArray(message.content)) continue;

		for (const part of message.content) {
			if (!isToolCallPart(part)) continue;
			const kind = ARTIFACT_TOOL_KINDS[part.toolName];
			if (!kind) continue;

			const result = asRecord(part.result);
			const args = asRecord(part.args);
			const { entityId, artifactId, legacyEntityId, failed } = describeArtifact(kind, result);
			if (failed || entityId == null) continue;
			const metadata = extractMetadataWithLegacyFormatCompatibility(kind, args, result);

			const key = artifactId == null ? `${kind}:${entityId}` : `artifact:${artifactId}`;
			byKey.set(key, {
				key,
				toolKind: kind,
				toolCallId: part.toolCallId,
				entityId,
				artifactId,
				legacyEntityId,
				...metadata,
			});
		}
	}

	return Array.from(byKey.values());
}

export function matchesPersistedArtifact(
	message: ArtifactCandidate,
	row: ArtifactListItem
): boolean {
	if (message.artifactId === row.artifact_id) return true;
	return (
		row.legacy != null &&
		message.toolKind === row.legacy.kind &&
		(message.legacyEntityId ?? message.entityId) === row.legacy.id
	);
}

function fromPersisted(row: ArtifactListItem, message: ArtifactCandidate): ChatArtifact {
	return {
		key: message.key,
		title: row.title,
		format: row.format,
		toolCallId: message.toolCallId,
		artifactId: row.artifact_id,
		legacyEntityId: row.legacy?.id,
		metadataStatus: "ready",
	};
}

/**
 * Resolve durable metadata and lazily upcast pre-explicit-format chat results.
 *
 * Compatibility is read-only: persisted Artifact rows supply missing formats,
 * while unmatched historical results stay hidden instead of using filename
 * inference. New results retain their optimistic message metadata.
 */
export function resolveArtifactRowsWithLegacyCompatibility(
	messageArtifacts: readonly ArtifactCandidate[],
	persisted: readonly ArtifactListItem[]
): ChatArtifact[] {
	const byArtifactId = new Map(persisted.map((row) => [row.artifact_id, row]));
	const byLegacy = new Map(
		persisted.flatMap((row) =>
			row.legacy ? [[`${row.legacy.kind}:${row.legacy.id}`, row] as const] : []
		)
	);

	return messageArtifacts.flatMap((message) => {
		const row =
			(message.artifactId == null ? undefined : byArtifactId.get(message.artifactId)) ??
			byLegacy.get(`${message.toolKind}:${message.legacyEntityId ?? message.entityId}`);
		if (row?.indexing_status === "deleting") return [];
		if (row) return [fromPersisted(row, message)];
		if (!message.format) return [];
		return [
			{
				key: message.key,
				title: message.title,
				format: message.format,
				toolCallId: message.toolCallId,
				artifactId: message.artifactId,
				legacyEntityId: message.legacyEntityId,
				metadataStatus: "pending",
			},
		];
	});
}
