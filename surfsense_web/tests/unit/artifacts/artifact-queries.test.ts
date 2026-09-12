import assert from "node:assert/strict";
import test from "node:test";
import { QueryClient } from "@tanstack/react-query";
import {
	artifactImageBlobQueryKey,
	artifactListQueryKey,
	artifactManifestQueryKey,
	invalidatePublishedArtifact,
} from "@/features/artifacts/api/artifact-queries";

test("artifact query keys preserve cache identity boundaries", () => {
	assert.deepEqual(artifactManifestQueryKey(7, 11), ["artifact-manifest", 7, 11]);
	assert.deepEqual(artifactImageBlobQueryKey(7, 11, null), [
		"artifact-image-blob",
		7,
		11,
		null,
		undefined,
	]);
	assert.deepEqual(artifactImageBlobQueryKey(7, 11, "share", 3), [
		"artifact-image-blob",
		7,
		11,
		"share",
		3,
	]);
	assert.deepEqual(artifactListQueryKey(7), ["artifact-list", 7]);
	assert.deepEqual(artifactListQueryKey(7, null), ["artifact-list", 7]);
	assert.deepEqual(artifactListQueryKey(7, 13), ["artifact-list", 7, 13]);
});

test("publishing removes artifact blobs and invalidates manifest and workspace lists", async () => {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const manifest = artifactManifestQueryKey(7, 11);
	const workspaceList = artifactListQueryKey(7);
	const threadList = artifactListQueryKey(7, 13);
	const blob = artifactImageBlobQueryKey(7, 11, null);
	const sharedBlob = artifactImageBlobQueryKey(7, 11, "share", 3);
	const otherBlob = artifactImageBlobQueryKey(7, 12, null);
	const otherWorkspaceList = artifactListQueryKey(8);

	queryClient.setQueryData(manifest, { revision: "old" });
	queryClient.setQueryData(workspaceList, ["workspace"]);
	queryClient.setQueryData(threadList, ["thread"]);
	queryClient.setQueryData(blob, "blob:private");
	queryClient.setQueryData(sharedBlob, "blob:shared");
	queryClient.setQueryData(otherBlob, "blob:other");
	queryClient.setQueryData(otherWorkspaceList, ["other"]);

	await invalidatePublishedArtifact(queryClient, 7, 11);

	assert.equal(queryClient.getQueryState(blob), undefined);
	assert.equal(queryClient.getQueryState(sharedBlob), undefined);
	assert.equal(queryClient.getQueryData(otherBlob), "blob:other");
	assert.equal(queryClient.getQueryData(manifest), undefined);
	assert.equal(queryClient.getQueryState(workspaceList)?.isInvalidated, true);
	assert.equal(queryClient.getQueryState(threadList)?.isInvalidated, true);
	assert.equal(queryClient.getQueryState(otherWorkspaceList)?.isInvalidated, false);

	queryClient.clear();
});
