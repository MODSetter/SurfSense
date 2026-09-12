import assert from "node:assert/strict";
import test from "node:test";

import type { GitRemote } from "@/contracts/types/git-remote.types";
import type { FolderDisplay } from "@/lib/documents/document-tree-types";
import {
	folderDeletionTouchesSync,
	gitMountFolderId,
	gitRepoLabel,
	isSyncedContent,
} from "@/lib/documents/git-synced-folders";

// Backend resolves the mount to the source-path folder (documents/GitHub/CREDO23/ai-lab/docs).
const remote: GitRemote = {
	provider: "github",
	url: "https://github.com/CREDO23/ai-lab.git",
	branch: "develop",
	sourcepath: "docs",
	mount_folder_id: 4,
};

function folder(id: number, name: string, parentId: number | null): FolderDisplay {
	return { id, name, position: "a", parentId, workspaceId: 1 };
}

// documents/ is the namespace root, so GitHub is a top-level folder row.
const tree: FolderDisplay[] = [
	folder(1, "GitHub", null),
	folder(2, "CREDO23", 1),
	folder(3, "ai-lab", 2),
	folder(4, "docs", 3), // the mount folder
	folder(5, "api", 4), // subfolder inside the source path
	folder(9, "Notes", null), // unrelated top-level folder
];

test("mount folder id comes straight from the backend", () => {
	assert.equal(gitMountFolderId(remote), 4);
	assert.equal(gitMountFolderId({ ...remote, mount_folder_id: null }), null);
	assert.equal(gitMountFolderId(undefined), null);
});

test("repo label strips scheme and .git for display", () => {
	assert.equal(gitRepoLabel(remote), "CREDO23/ai-lab");
});

test("folder deletion is guarded for the mount, its ancestors, and its descendants", () => {
	const hits = (id: number) => folderDeletionTouchesSync(tree, id, 4);
	assert.equal(hits(4), true, "the mount folder itself");
	assert.equal(hits(5), true, "a synced subfolder (descendant)");
	assert.equal(hits(3), true, "the repo folder (ancestor of the mount)");
	assert.equal(hits(1), true, "the forge root (ancestor of the mount)");
	assert.equal(hits(9), false, "an unrelated folder");
	assert.equal(folderDeletionTouchesSync(tree, 4, null), false, "no mount means no guard");
});

test("synced content is the mount folder or anything inside it, not its ancestors", () => {
	assert.equal(isSyncedContent(tree, 4, 4), true, "the mount folder itself");
	assert.equal(isSyncedContent(tree, 5, 4), true, "a synced subfolder");
	assert.equal(isSyncedContent(tree, 3, 4), false, "an ancestor only contains synced content");
	assert.equal(isSyncedContent(tree, 1, 4), false, "the forge root only contains it");
	assert.equal(isSyncedContent(tree, 9, 4), false, "an unrelated folder");
	assert.equal(isSyncedContent(tree, null, 4), false, "a root-level doc");
	assert.equal(isSyncedContent(tree, 4, null), false, "no mount means nothing is synced");
});
