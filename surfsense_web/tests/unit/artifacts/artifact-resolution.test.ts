import assert from "node:assert/strict";
import test from "node:test";
import {
	ARTIFACT_GROUP_ORDER,
	getArtifactFormatMeta,
	isArtifactDownloadable,
	normalizeArtifactFormat,
} from "@/features/artifacts/lib/artifact-format-catalog";
import { resolveArtifactRenderer } from "@/features/artifacts/lib/artifact-resolution";

const semanticFormats = new Set(["flashcards", "mindmap", "quiz"]);
const mimeTypes = new Set(["application/pdf", "image/png", "video/mp4"]);

function resolve(overrides: Partial<Parameters<typeof resolveArtifactRenderer>[0]> = {}) {
	return resolveArtifactRenderer({
		format: "file",
		primaryMimeType: null,
		hasPrimary: false,
		hasMarkdown: false,
		semanticFormats,
		mimeTypes,
		...overrides,
	});
}

test("renderer resolution preserves semantic, MIME, and markdown precedence", () => {
	assert.deepEqual(
		resolve({
			format: " FlashCards ",
			primaryMimeType: "application/pdf",
			hasPrimary: true,
			hasMarkdown: true,
		}),
		{ kind: "semantic", key: "flashcards" }
	);
	assert.deepEqual(
		resolve({ primaryMimeType: "application/pdf", hasPrimary: true, hasMarkdown: true }),
		{ kind: "mime", key: "application/pdf" }
	);
	assert.deepEqual(
		resolve({ primaryMimeType: "application/x-unknown", hasPrimary: true, hasMarkdown: true }),
		{ kind: "unviewable" }
	);
	assert.deepEqual(resolve({ hasMarkdown: true }), { kind: "markdown" });
	assert.deepEqual(resolve(), { kind: "unviewable" });
});

test("format normalization and metadata retain current semantic and media behavior", () => {
	assert.equal(normalizeArtifactFormat("  MiNdMaP "), "mindmap");
	assert.equal(normalizeArtifactFormat(null), "file");
	assert.equal(isArtifactDownloadable(" FlashCards "), false);
	assert.equal(isArtifactDownloadable("quiz"), false);
	assert.equal(isArtifactDownloadable("mindmap"), true);

	const flashcards = getArtifactFormatMeta("flashcards");
	assert.deepEqual(
		{
			label: flashcards.label,
			detailLabel: flashcards.detailLabel,
			groupKey: flashcards.groupKey,
			viewingMode: flashcards.viewingMode,
		},
		{
			label: "Interactive",
			detailLabel: "Flashcards",
			groupKey: "files",
			viewingMode: "viewer",
		}
	);
	const quiz = getArtifactFormatMeta("quiz");
	assert.equal(quiz.label, "Interactive");
	assert.equal(quiz.detailLabel, "Quiz");
	assert.deepEqual(
		resolve({ format: "quiz", primaryMimeType: "application/json", hasPrimary: true }),
		{ kind: "semantic", key: "quiz" }
	);

	const podcast = getArtifactFormatMeta("podcast");
	const image = getArtifactFormatMeta("image");
	const infographic = getArtifactFormatMeta("infographic");
	assert.equal(podcast.groupKey, "podcasts");
	assert.equal(podcast.viewingMode, "inline-media");
	assert.equal(image.groupKey, "images");
	assert.equal(image.viewingMode, "inline-media");
	assert.equal(infographic.label, "Infographic");
	assert.equal(infographic.detailLabel, "PNG");
	assert.equal(infographic.groupKey, "images");
	assert.equal(infographic.viewingMode, "viewer");
	assert.deepEqual(
		resolve({ format: "infographic", primaryMimeType: "image/png", hasPrimary: true }),
		{ kind: "mime", key: "image/png" }
	);
	assert.deepEqual(ARTIFACT_GROUP_ORDER, [
		"files",
		"podcasts",
		"videos",
		"presentations",
		"images",
	]);
});

test("unknown formats fall back to file metadata without losing their detail label", () => {
	const meta = getArtifactFormatMeta("  glb ");
	assert.equal(meta.label, "File");
	assert.equal(meta.detailLabel, "GLB");
	assert.equal(meta.groupKey, "files");
	assert.equal(meta.groupLabel, "Files");
	assert.equal(meta.viewingMode, "viewer");
});
