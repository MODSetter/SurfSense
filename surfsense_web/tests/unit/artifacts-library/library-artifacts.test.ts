import assert from "node:assert/strict";
import test from "node:test";
import type { ArtifactListItem } from "@/features/artifacts/model/artifact";
import { projectLibraryArtifacts } from "@/features/artifacts-library/hooks/use-library-artifacts";

function artifact(overrides: Partial<ArtifactListItem> = {}): ArtifactListItem {
	return {
		artifact_id: 1,
		document_id: 10,
		title: "Artifact",
		format: " PDF ",
		generation: 1,
		indexing_status: "ready",
		thread_id: 20,
		created_at: "2026-01-01T00:00:00Z",
		updated_at: null,
		...overrides,
	};
}

test("projects, normalizes, and sorts persisted artifacts for the library", () => {
	const projected = projectLibraryArtifacts([
		artifact(),
		artifact({
			artifact_id: 2,
			title: "Newer",
			format: "FLASHCARDS",
			indexing_status: "processing",
			created_at: "2026-02-01T00:00:00Z",
		}),
	]);

	assert.deepEqual(
		projected.map(({ artifactId, format, status }) => ({ artifactId, format, status })),
		[
			{ artifactId: 2, format: "flashcards", status: "running" },
			{ artifactId: 1, format: "pdf", status: "ready" },
		]
	);
});

test("maps failed persisted artifacts to the library error state", () => {
	assert.equal(
		projectLibraryArtifacts([artifact({ indexing_status: "failed" })])[0]?.status,
		"error"
	);
});
