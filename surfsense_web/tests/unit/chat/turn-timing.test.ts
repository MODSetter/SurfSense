import assert from "node:assert/strict";
import test from "node:test";

import { resolveTurnTimingDisplay } from "@/features/chat-messages/timeline/turn-timing-state";

test("shows a placeholder until the backend sends timing", () => {
	assert.deepEqual(resolveTurnTimingDisplay(null, true), { phase: "placeholder" });
});

test("projects only an authoritative running snapshot", () => {
	const projection = { baseDurationMs: 1200, receivedAtPerformanceMs: 500 };
	assert.deepEqual(
		resolveTurnTimingDisplay(
			{
				timing: { status: "running", activeDurationMs: 1200 },
				projection,
			},
			true
		),
		{
			phase: "live",
			timing: { status: "running", activeDurationMs: 1200 },
			projection,
		}
	);
});

test("keeps paused and completed backend snapshots static", () => {
	assert.deepEqual(
		resolveTurnTimingDisplay(
			{
				timing: { status: "paused", activeDurationMs: 2400 },
				projection: null,
			},
			false
		),
		{
			phase: "static",
			timing: { status: "paused", activeDurationMs: 2400 },
		}
	);
	assert.deepEqual(
		resolveTurnTimingDisplay(
			{
				timing: { status: "completed", activeDurationMs: 5000 },
				projection: null,
			},
			false
		),
		{
			phase: "static",
			timing: { status: "completed", activeDurationMs: 5000 },
		}
	);
});

test("freezes presentation when the terminal backend frame is missing", () => {
	assert.deepEqual(
		resolveTurnTimingDisplay(
			{
				timing: { status: "running", activeDurationMs: 2400 },
				projection: { baseDurationMs: 2400, receivedAtPerformanceMs: 500 },
			},
			false,
			3100
		),
		{
			phase: "frozen",
			timing: { status: "completed", activeDurationMs: 3100 },
		}
	);
});
