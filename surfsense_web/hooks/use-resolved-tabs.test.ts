import assert from "node:assert/strict";
import { test } from "node:test";
import {
	getMissingCompleteChatIds,
	resolveTabPointers,
	type ResolvedTab,
} from "./use-resolved-tabs";

// Run with: pnpm exec tsx --test hooks/use-resolved-tabs.test.ts
test("does not prune unresolved chat tabs before Zero completes", () => {
	const missing = getMissingCompleteChatIds({
		tabs: [{ id: "chat-42", type: "chat", entityId: 42, workspaceId: 7 }],
		threadRows: [],
		resultType: "unknown",
	});

	assert.equal(missing.size, 0);
});

test("prunes unresolved chat tabs only after Zero completes", () => {
	const missing = getMissingCompleteChatIds({
		tabs: [
			{ id: "chat-42", type: "chat", entityId: 42, workspaceId: 7 },
			{ id: "chat-43", type: "chat", entityId: 43, workspaceId: 7 },
		],
		threadRows: [{ id: 43, title: "Present", visibility: "PRIVATE" }],
		resultType: "complete",
	});

	assert.deepEqual([...missing], [42]);
});

test("merges pointer tabs with synced row titles", () => {
	const resolved = resolveTabPointers({
		tabs: [
			{ id: "chat-42", type: "chat", entityId: 42, workspaceId: 7 },
			{ id: "doc-9", type: "document", entityId: 9, workspaceId: 7 },
		],
		threadRows: [{ id: 42, title: "Live chat title", visibility: "SEARCH_SPACE" }],
		documentRows: [{ id: 9, title: "Live document title" }],
	});

	assert.deepEqual(
		resolved.map((tab): Pick<ResolvedTab, "id" | "title"> => ({
			id: tab.id,
			title: tab.title,
		})),
		[
			{ id: "chat-42", title: "Live chat title" },
			{ id: "doc-9", title: "Live document title" },
		]
	);
});
