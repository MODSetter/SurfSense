import assert from "node:assert/strict";
import test from "node:test";

import { QueryClient } from "@tanstack/react-query";
import {
	artifactImageBlobQueryKey,
	artifactListQueryKey,
	artifactManifestQueryKey,
	invalidatePublishedArtifact,
} from "@/features/artifacts/artifact-query";
import {
	collectArtifacts,
	enrichArtifactRows,
} from "@/features/chat-artifacts/lib/collect-artifacts";
import { buildTurnRenderItems } from "@/features/chat-messages/timeline/grouping";

const bodyTools = new Set(["save_artifact"]);

test("only a successful save is rendered as a product body card", () => {
	for (const result of [
		undefined,
		{ status: "failed", artifact_id: 12 },
		{ status: "saved", artifact_id: null },
	]) {
		const [item] = buildTurnRenderItems({
			parts: [
				{
					type: "tool-call",
					toolName: "save_artifact",
					toolCallId: "save-1",
					result,
				},
			],
			bodyToolNames: bodyTools,
			showReasoning: true,
			threadRunning: false,
		});
		assert.equal(item?.kind, "segment");
	}

	const [saved] = buildTurnRenderItems({
		parts: [
			{
				type: "tool-call",
				toolName: "save_artifact",
				toolCallId: "save-2",
				result: { status: "saved", artifact_id: 12 },
			},
		],
		bodyToolNames: bodyTools,
		showReasoning: true,
		threadRunning: false,
	});
	assert.equal(saved?.kind, "body-tool");
});

test("revisions share one sidebar row with latest metadata and card target", () => {
	const messages = [
		{
			role: "assistant",
			content: [
				{
					type: "tool-call",
					toolName: "save_artifact",
					toolCallId: "old-card",
					args: { title: "Old title" },
					result: {
						status: "saved",
						artifact_id: 42,
						title: "Old title",
						files: [{ role: "primary", filename: "old.docx" }],
					},
				},
			],
		},
		{
			role: "assistant",
			content: [
				{
					type: "tool-call",
					toolName: "save_artifact",
					toolCallId: "failed-card",
					args: { title: "Broken revision" },
					result: { status: "failed", artifact_id: 42, error: "boom" },
				},
				{
					type: "tool-call",
					toolName: "save_artifact",
					toolCallId: "latest-card",
					args: { title: "New title" },
					result: {
						status: "saved",
						artifact_id: 42,
						title: "New title",
						files: [{ role: "primary", filename: "new.pdf" }],
					},
				},
			],
		},
	] as never;

	const candidates = collectArtifacts(messages);
	assert.equal(candidates.length, 1);
	assert.equal(candidates[0]?.toolCallId, "latest-card");

	const [row] = enrichArtifactRows(candidates, [
		{
			artifact_id: 42,
			document_id: 99,
			title: "Canonical latest title",
			format: "pdf",
			generation: 2,
			indexing_status: "ready",
			created_at: "2026-08-18T00:00:00Z",
			updated_at: "2026-08-18T00:01:00Z",
			thread_id: 7,
		},
	]);
	assert.equal(row?.title, "Canonical latest title");
	assert.equal(row?.format, "pdf");
	assert.equal(row?.toolCallId, "latest-card");
});

test("publication clears revision-sensitive caches and invalidates lists", async () => {
	const client = new QueryClient();
	const workspaceId = 3;
	const artifactId = 42;
	const manifestKey = artifactManifestQueryKey(workspaceId, artifactId);
	const listKey = artifactListQueryKey(workspaceId);
	const threadListKey = artifactListQueryKey(workspaceId, 7);
	const libraryKey = ["artifacts-library", workspaceId] as const;
	const imageKey = artifactImageBlobQueryKey(workspaceId, artifactId, null, 100);

	for (const key of [manifestKey, listKey, threadListKey, libraryKey, imageKey]) {
		client.setQueryData(key, { cached: true });
	}

	await invalidatePublishedArtifact(client, workspaceId, artifactId);

	assert.equal(client.getQueryData(manifestKey), undefined);
	assert.equal(client.getQueryData(imageKey), undefined);
	assert.equal(client.getQueryState(listKey)?.isInvalidated, true);
	assert.equal(client.getQueryState(threadListKey)?.isInvalidated, true);
	assert.equal(client.getQueryState(libraryKey)?.isInvalidated, true);
});
