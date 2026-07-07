import assert from "node:assert/strict";
import { test } from "node:test";
import { migrateLegacyTabs } from "./migrate-tabs";

// Run with: pnpm exec tsx --test atoms/tabs/migrate-tabs.test.ts
test("maps legacy searchSpaceId to workspaceId on read", () => {
	const migrated = migrateLegacyTabs({
		tabs: [{ id: "chat-new", type: "chat", searchSpaceId: 7 } as never],
		activeTabId: "chat-new",
	});
	const tab = migrated.tabs[0] as { workspaceId?: number };
	assert.equal(tab.workspaceId, 7);
});

test("leaves an already-migrated workspaceId untouched", () => {
	const migrated = migrateLegacyTabs({
		tabs: [{ id: "d1", type: "document", workspaceId: 3, searchSpaceId: 9 } as never],
	});
	const tab = migrated.tabs[0] as { workspaceId?: number };
	assert.equal(tab.workspaceId, 3);
});
