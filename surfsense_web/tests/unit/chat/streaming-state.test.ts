import assert from "node:assert/strict";
import test from "node:test";

import { type ContentPartsState, upsertActivityTiming } from "@/lib/chat/streaming-state";

function state(): ContentPartsState {
	return {
		contentParts: [],
		currentTextPartIndex: -1,
		currentReasoningPartIndex: -1,
		toolCallIndices: new Map(),
		activities: new Map(),
	};
}

test("duplicate running snapshots preserve the projection anchor", () => {
	const current = state();

	assert.equal(
		upsertActivityTiming(current, { status: "running", activeDurationMs: 1000 }, 500),
		true
	);
	assert.equal(
		upsertActivityTiming(current, { status: "running", activeDurationMs: 1000 }, 900),
		false
	);
	assert.deepEqual(current.activityTimingProjection, {
		baseDurationMs: 1000,
		receivedAtPerformanceMs: 500,
	});
});

test("stale snapshots cannot replace timing or its projection", () => {
	const current = state();
	upsertActivityTiming(current, { status: "running", activeDurationMs: 1000 }, 500);

	assert.equal(
		upsertActivityTiming(current, { status: "running", activeDurationMs: 900 }, 900),
		false
	);
	assert.deepEqual(current.activityTiming, {
		status: "running",
		activeDurationMs: 1000,
	});
	assert.deepEqual(current.activityTimingProjection, {
		baseDurationMs: 1000,
		receivedAtPerformanceMs: 500,
	});
});

test("paused and completed snapshots clear browser projection", () => {
	const current = state();
	upsertActivityTiming(current, { status: "running", activeDurationMs: 1000 }, 500);
	upsertActivityTiming(current, { status: "paused", activeDurationMs: 1200 }, 700);
	assert.equal(current.activityTimingProjection, undefined);

	upsertActivityTiming(current, { status: "running", activeDurationMs: 1200 }, 900);
	upsertActivityTiming(current, { status: "completed", activeDurationMs: 1500 }, 1100);
	assert.equal(current.activityTimingProjection, undefined);
});
