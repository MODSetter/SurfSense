import type { ThreadMessageLike } from "@assistant-ui/react";
import { extension } from "@/features/artifacts/file-format";
import type { ArtifactListItem } from "@/features/artifacts/model";
import {
	ARTIFACT_TOOL_KINDS,
	type ArtifactKind,
	type ArtifactStatus,
	type ChatArtifact,
} from "../model/artifact";

interface ToolCallPart {
	type: "tool-call";
	toolCallId: string;
	toolName: string;
	args?: Record<string, unknown>;
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

function firstString(...values: unknown[]): string | null {
	for (const value of values) {
		if (typeof value === "string" && value.trim().length > 0) return value;
	}
	return null;
}

function numericId(value: unknown): number | null {
	return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatFromFilename(value: unknown): string | null {
	if (typeof value !== "string") return null;
	const format = extension(value);
	return format === "FILE" ? null : format.toLowerCase();
}

function primaryFilename(result: Record<string, unknown>): string | null {
	if (!Array.isArray(result.files)) return null;
	for (const file of result.files) {
		const record = asRecord(file);
		if (record.role === "primary" && typeof record.filename === "string") return record.filename;
	}
	return null;
}

type Described = {
	title: string;
	format: string;
	entityId: number | null;
	artifactId?: number;
	legacyEntityId?: number;
	status: ArtifactStatus;
};

/** Extracts entity id, title, and status for a single deliverable tool call. */
function describeArtifact(
	kind: ArtifactKind,
	args: Record<string, unknown>,
	result: Record<string, unknown>
): Described {
	const resultStatus = typeof result.status === "string" ? result.status : null;
	const failed = resultStatus === "failed" || resultStatus === "error" || !!result.error;

	switch (kind) {
		case "file": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			return {
				title: firstString(result.title, args.title) ?? "Document",
				format:
					formatFromFilename(primaryFilename(result)) ??
					formatFromFilename(args.path) ??
					"markdown",
				entityId: artifactId ?? null,
				artifactId,
				status: failed ? "error" : artifactId != null ? "ready" : "running",
			};
		}
		case "podcast": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			const legacyEntityId = numericId(result.podcast_id) ?? undefined;
			const entityId = artifactId ?? legacyEntityId ?? null;
			return {
				title: firstString(result.title, args.podcast_title) ?? "Podcast",
				format: "podcast",
				entityId,
				artifactId,
				legacyEntityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "video": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			const legacyEntityId = numericId(result.video_presentation_id) ?? undefined;
			const entityId = artifactId ?? legacyEntityId ?? null;
			return {
				title: firstString(result.title, args.video_title) ?? "Presentation",
				format: "video",
				entityId,
				artifactId,
				legacyEntityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "image": {
			const artifactId = numericId(result.artifact_id) ?? undefined;
			return {
				title: firstString(result.title, args.prompt) ?? "Image",
				format: "image",
				entityId: artifactId ?? null,
				artifactId,
				status: failed ? "error" : artifactId != null ? "ready" : "running",
			};
		}
	}
}

/**
 * Aggregate the deliverable artifacts referenced across a thread's messages.
 *
 * Scans assistant tool-call parts, keeps recognized deliverable tools, and
 * dedupes by backing entity (so a revised artifact collapses to one entry,
 * refreshed in place to keep chronological order). Errored deliverables are
 * dropped — they have nothing to open or jump to.
 */
export function collectArtifacts(messages: readonly ThreadMessageLike[]): ChatArtifact[] {
	const byKey = new Map<string, ChatArtifact>();

	for (const message of messages) {
		if (message.role !== "assistant" || !Array.isArray(message.content)) continue;

		for (const part of message.content) {
			if (!isToolCallPart(part)) continue;
			const kind = ARTIFACT_TOOL_KINDS[part.toolName];
			if (!kind) continue;

			const args = asRecord(part.args);
			const result = asRecord(part.result);
			const { title, format, entityId, artifactId, legacyEntityId, status } = describeArtifact(
				kind,
				args,
				result
			);
			if (status === "error") continue;

			const key = entityId != null ? `${kind}:${entityId}` : part.toolCallId;
			byKey.set(key, {
				key,
				kind,
				title,
				format,
				status,
				toolCallId: part.toolCallId,
				entityId,
				artifactId,
				legacyEntityId,
			});
		}
	}

	return Array.from(byKey.values());
}

function kindFromFormat(format: string): ArtifactKind {
	return format === "podcast" || format === "video" || format === "image" ? format : "file";
}

export function matchesPersistedArtifact(message: ChatArtifact, row: ArtifactListItem): boolean {
	if (message.artifactId === row.artifact_id) return true;
	return (
		row.legacy != null &&
		message.kind === row.legacy.kind &&
		(message.legacyEntityId ?? message.entityId) === row.legacy.id
	);
}

function fromPersisted(row: ArtifactListItem, message: ChatArtifact): ChatArtifact {
	const kind = kindFromFormat(row.format);
	return {
		key: `${kind}:${row.artifact_id}`,
		kind,
		title: row.title,
		format: row.format,
		status: row.indexing_status === "failed" ? "error" : "ready",
		toolCallId: message.toolCallId,
		entityId: row.artifact_id,
		artifactId: row.artifact_id,
		legacyEntityId: row.legacy?.id,
	};
}

/** Reconcile durable thread artifacts with in-flight message tool calls. */
export function mergePersistedArtifacts(
	messageArtifacts: readonly ChatArtifact[],
	persisted: readonly ArtifactListItem[]
): ChatArtifact[] {
	return messageArtifacts.map((message) => {
		const row = persisted.find((candidate) => matchesPersistedArtifact(message, candidate));
		if (!row) return message;
		return fromPersisted(row, message);
	});
}
