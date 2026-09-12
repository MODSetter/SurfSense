import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
	DEFAULT_RETRIEVAL_SCOPE,
	isRetrievalScope,
	RETRIEVAL_SCOPES,
	scopeForMentionKinds,
} from "../../../contracts/types/retrieval-scope.types";
import { parseRetrievalScopeCookie } from "../../../lib/chat/retrieval-scope-preferences";

test("retrieval scope contract is closed and defaults to documents", () => {
	assert.deepEqual(RETRIEVAL_SCOPES, ["documents", "web", "all"]);
	assert.equal(DEFAULT_RETRIEVAL_SCOPE, "documents");
	assert.equal(isRetrievalScope("all"), true);
	assert.equal(isRetrievalScope("invalid"), false);
	assert.equal(scopeForMentionKinds("documents", ["connector"]), "all");
	assert.equal(scopeForMentionKinds("web", ["doc"]), "all");
	assert.equal(scopeForMentionKinds("web", ["connector"]), "web");
});

test("cookie preference is accepted only for the matching user", () => {
	const value = encodeURIComponent("user-1:all");
	assert.equal(parseRetrievalScopeCookie(value, "user-1"), "all");
	assert.equal(parseRetrievalScopeCookie(value, "user-2"), "documents");
	assert.equal(parseRetrievalScopeCookie("broken", "user-1"), "documents");
});

test("new, resume, and regenerate requests carry retrieval_scope", () => {
	const source = readFileSync(
		new URL("../../../lib/chat/stream-engine/engine.ts", import.meta.url),
		"utf8"
	);
	assert.equal(
		source.match(/retrieval_scope:/g)?.length,
		3,
		"every chat mutation must send its effective retrieval scope"
	);
});

test("composer snapshots scope before send", () => {
	const source = readFileSync(
		new URL("../../../components/assistant-ui/thread.tsx", import.meta.url),
		"utf8"
	);
	assert.ok(source.includes("setSubmittedRetrievalScope(effectiveScope)"));
	assert.ok(source.includes("scopeForMentionKinds("));
});

test("composer reconciles scope when mentions arrive outside the inline picker", () => {
	const source = readFileSync(
		new URL("../../../components/assistant-ui/thread.tsx", import.meta.url),
		"utf8"
	);
	const scopeSync = source.lastIndexOf("const effectiveScope = scopeForMentionKinds(");
	const mentionSync = source.indexOf("const nextDocsMap", scopeSync);

	assert.notEqual(scopeSync, -1);
	assert.notEqual(mentionSync, -1);
});

test("dashboard seeds scope from the server cookie before rendering chat", () => {
	const layout = readFileSync(
		new URL("../../../app/dashboard/[workspace_id]/layout.tsx", import.meta.url),
		"utf8"
	);
	const clientLayout = readFileSync(
		new URL("../../../app/dashboard/[workspace_id]/client-layout.tsx", import.meta.url),
		"utf8"
	);
	assert.ok(layout.includes("initialRetrievalScope={initialRetrievalScope}"));
	assert.ok(clientLayout.includes("initialScope={initialRetrievalScope}"));
});

test("segmented control renders its indicator position without client measurement", () => {
	const source = readFileSync(
		new URL("../../../components/ui/segmented-control.tsx", import.meta.url),
		"utf8"
	);
	assert.ok(source.includes("const selectedIndex = options.findIndex"));
	assert.ok(source.includes("Math.max(selectedIndex, 0) * 100"));
	assert.ok(!source.includes("requestAnimationFrame"));
	assert.ok(!source.includes("ResizeObserver"));
});
