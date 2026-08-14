import type { ThreadMessageLike } from "@assistant-ui/react";
import type { ArtifactListItem } from "@/features/artifacts/model";
import { ARTIFACT_TOOL_KINDS, type ArtifactToolKind, type ChatArtifact } from "../model/artifact";

interface ToolCallPart {
	type: "tool-call";
	toolCallId: string;
	toolName: string;
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
				failed,
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
			const { entityId, artifactId, legacyEntityId, failed } = describeArtifact(kind, result);
			if (failed || entityId == null) continue;

			const key = `${kind}:${entityId}`;
			byKey.set(key, {
				key,
				toolKind: kind,
				toolCallId: part.toolCallId,
				entityId,
				artifactId,
				legacyEntityId,
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
		key: `artifact:${row.artifact_id}`,
		title: row.title,
		format: row.format,
		toolCallId: message.toolCallId,
		artifactId: row.artifact_id,
		legacyEntityId: row.legacy?.id,
	};
}

/** Reconcile durable thread artifacts with in-flight message tool calls. */
export function mergePersistedArtifacts(
	messageArtifacts: readonly ArtifactCandidate[],
	persisted: readonly ArtifactListItem[]
): ChatArtifact[] {
	return messageArtifacts.flatMap((message) => {
		const row = persisted.find((candidate) => matchesPersistedArtifact(message, candidate));
		return row && row.indexing_status !== "deleting" ? [fromPersisted(row, message)] : [];
	});
}
