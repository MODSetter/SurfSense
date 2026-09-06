import assert from "node:assert/strict";
import test from "node:test";

import { providerDiagnosticsOf } from "@/lib/chat/chat-error-classifier";
import {
	processSharedStreamEvent,
	type SharedStreamEventContext,
} from "@/lib/chat/stream-pipeline";
import type { ContentPartsState, SSEEvent } from "@/lib/chat/streaming-state";

/**
 * `MODEL_PROVIDER_UNAVAILABLE` is one code covering five upstream categories,
 * so these three fields are the only thing that tells them apart in telemetry.
 * They cross two module boundaries (stream pipeline attaches, engine reads),
 * and a silent drop anywhere between leaves the failure undiagnosable without
 * backend log access — which is the state this test exists to prevent.
 */

function context(): SharedStreamEventContext {
	const contentPartsState: ContentPartsState = {
		contentParts: [],
		currentTextPartIndex: -1,
		currentReasoningPartIndex: -1,
		toolCallIndices: new Map(),
		activities: new Map(),
	};
	return {
		contentPartsState,
		toolsWithUI: { has: () => false } as unknown as SharedStreamEventContext["toolsWithUI"],
		scheduleFlush: () => {},
		forceFlush: () => {},
	};
}

/** Run an error frame through the real pipeline and return what it threw. */
function thrownFor(event: Extract<SSEEvent, { type: "error" }>): unknown {
	try {
		processSharedStreamEvent(event, context());
	} catch (error) {
		return error;
	}
	throw new Error("error frame did not throw");
}

test("provider diagnostics survive the stream pipeline to the telemetry reader", () => {
	const thrown = thrownFor({
		type: "error",
		message: "The selected model provider is temporarily unavailable.",
		errorCode: "MODEL_PROVIDER_UNAVAILABLE",
		provider_error_category: "timeout",
		provider_status_code: 504,
		provider_error_type: "upstream_timeout",
	});

	assert.deepEqual(providerDiagnosticsOf(thrown), {
		provider_error_category: "timeout",
		provider_status_code: 504,
		provider_error_type: "upstream_timeout",
	});
});

test("the five collapsed categories stay distinguishable", () => {
	const categories = [
		"timeout",
		"provider_unavailable",
		"bad_gateway",
		"connection_failed",
		"server_error",
	];

	const seen = categories.map(
		(category) =>
			providerDiagnosticsOf(
				thrownFor({
					type: "error",
					message: "The selected model provider is temporarily unavailable.",
					errorCode: "MODEL_PROVIDER_UNAVAILABLE",
					provider_error_category: category,
				})
			).provider_error_category
	);

	assert.deepEqual(seen, categories);
});

test("a frame carrying no diagnostics adds no telemetry properties", () => {
	const thrown = thrownFor({
		type: "error",
		message: "Something went wrong",
		errorCode: "SERVER_ERROR",
	});

	assert.deepEqual(providerDiagnosticsOf(thrown), {});
});

test("wrong-typed fields are dropped rather than forwarded", () => {
	const thrown = thrownFor({
		type: "error",
		message: "The selected model provider is temporarily unavailable.",
		errorCode: "MODEL_PROVIDER_UNAVAILABLE",
		// A status code arriving as a string would otherwise reach PostHog and
		// split the property into two types, which breaks aggregation on it.
		provider_status_code: "504" as unknown as number,
		provider_error_category: "timeout",
	});

	assert.deepEqual(providerDiagnosticsOf(thrown), {
		provider_error_category: "timeout",
	});
});

test("non-object errors read as empty instead of throwing", () => {
	for (const value of [null, undefined, "boom", 42, new Error("plain")]) {
		assert.deepEqual(providerDiagnosticsOf(value), {});
	}
});
