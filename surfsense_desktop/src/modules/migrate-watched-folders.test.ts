import assert from "node:assert/strict";
import { test } from "node:test";
import { migrateWatchedFolderConfigs } from "./migrate-watched-folders.ts";

// Run with: node --test src/modules/migrate-watched-folders.test.ts
test("maps legacy searchSpaceId to workspaceId and flags migration", () => {
  const { configs, migrated } = migrateWatchedFolderConfigs<{ workspaceId?: number }>([
    { path: "/tmp/a", searchSpaceId: 42 },
  ]);
  assert.equal(migrated, true);
  assert.equal(configs[0].workspaceId, 42);
  assert.equal("searchSpaceId" in (configs[0] as object), false);
});

test("leaves configs that already have workspaceId untouched", () => {
  const { configs, migrated } = migrateWatchedFolderConfigs<{ workspaceId?: number }>([
    { path: "/tmp/b", workspaceId: 5 },
  ]);
  assert.equal(migrated, false);
  assert.equal(configs[0].workspaceId, 5);
});
