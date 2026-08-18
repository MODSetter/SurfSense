import assert from "node:assert/strict";
import test from "node:test";

import {
	documentDownloadTarget,
	isDownloadableDocumentType,
} from "@/lib/documents/document-download";

test("only uploads and artifacts offer a download", () => {
	assert.equal(isDownloadableDocumentType("FILE"), true);
	assert.equal(isDownloadableDocumentType("ARTIFACT"), true);
	assert.equal(isDownloadableDocumentType("LOCAL_FOLDER_FILE"), false);
	assert.equal(isDownloadableDocumentType("SLACK_CONNECTOR"), false);
	assert.equal(isDownloadableDocumentType("NOTE"), false);
});

test("uploads download their stored original", () => {
	assert.deepEqual(
		documentDownloadTarget({ id: 7, title: "Report.pdf", document_type: "FILE" }, 3),
		{ path: "/api/v1/documents/7/download-original", filename: "Report.pdf" }
	);
});

test("artifacts download from the workspace artifact endpoint with a format suffix", () => {
	assert.deepEqual(
		documentDownloadTarget({ id: 7, title: "Q3 deck", document_type: "ARTIFACT" }, 3, {
			artifact_id: 42,
			format: "pptx",
		}),
		{ path: "/api/v1/workspaces/3/artifacts/42/download", filename: "Q3 deck.pptx" }
	);
});

test("an artifact that has not been indexed yet has nothing to download", () => {
	assert.equal(
		documentDownloadTarget({ id: 7, title: "Q3 deck", document_type: "ARTIFACT" }, 3),
		null
	);
});
