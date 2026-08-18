import assert from "node:assert/strict";
import test from "node:test";

import { getActivityPresentation } from "@/features/chat-messages/timeline/presentation";
import {
	extractActivityJournal,
	mergeActivityTiming,
	parseActivityJournalPart,
} from "@/lib/chat/activity-journal";

const child = {
	id: "act-child",
	sequence: 2,
	kind: "file.write",
	status: "completed",
	title: "Wrote file",
	category: "file",
	iconKey: "file-plus",
	startedAt: "2026-01-01T00:00:00Z",
	completedAt: "2026-01-01T00:00:01Z",
} as const;

test("parses persisted canonical activities with timing", () => {
	const parsed = parseActivityJournalPart({
		type: "data-activities",
		data: {
			activities: [child],
			timing: { status: "completed", activeDurationMs: 1250 },
		},
	});

	assert.deepEqual(parsed?.activities, [child]);
	assert.deepEqual(parsed?.timing, {
		status: "completed",
		activeDurationMs: 1250,
	});
});

test("parses assistant-ui normalized activities with timing", () => {
	const parsed = parseActivityJournalPart({
		type: "data",
		name: "activities",
		data: {
			activities: [child],
			timing: { status: "paused", activeDurationMs: 900 },
		},
	});

	assert.deepEqual(parsed?.activities, [child]);
	assert.deepEqual(parsed?.timing, {
		status: "paused",
		activeDurationMs: 900,
	});
});

test("uses progress titles while silently dropping legacy detail bullets", () => {
	const parsed = parseActivityJournalPart({
		type: "data-activities",
		data: {
			activities: [
				{
					...child,
					status: "running",
					title: "Checking the artifact",
					progressTitle: "Rendering preview",
					details: ["Old progress detail"],
					completedAt: undefined,
				},
			],
		},
	});
	const activity = parsed?.activities[0];

	assert.equal(activity?.progressTitle, "Rendering preview");
	assert.equal("details" in (activity ?? {}), false);
	assert.deepEqual(activity ? getActivityPresentation(activity, true) : null, {
		status: "running",
		title: "Rendering preview",
	});
	assert.deepEqual(activity ? getActivityPresentation(activity, false) : null, {
		status: "interrupted",
		title: "Checking the artifact",
	});
});

test("keeps terminal activity snapshots over stale running snapshots", () => {
	const journal = extractActivityJournal([
		{
			type: "data-activities",
			data: { activities: [child] },
		},
		{
			type: "data",
			name: "activities",
			data: {
				activities: [
					{
						...child,
						status: "running",
						title: "Writing file",
						completedAt: undefined,
					},
				],
			},
		},
	]);

	assert.equal(journal.byId.get(child.id)?.status, "completed");
	assert.equal(journal.byId.get(child.id)?.title, "Wrote file");
});

test("keeps timing duration monotonic while allowing HITL resume", () => {
	const paused = { status: "paused", activeDurationMs: 900 } as const;

	assert.deepEqual(mergeActivityTiming(paused, { status: "running", activeDurationMs: 900 }), {
		status: "running",
		activeDurationMs: 900,
	});
	assert.deepEqual(
		mergeActivityTiming(paused, { status: "running", activeDurationMs: 899 }),
		paused
	);
});

test("completed timing is immutable against delayed frames", () => {
	const completed = { status: "completed", activeDurationMs: 1250 } as const;

	assert.equal(
		mergeActivityTiming(completed, { status: "completed", activeDurationMs: 1500 }),
		completed
	);
	assert.equal(
		mergeActivityTiming(completed, { status: "running", activeDurationMs: 1500 }),
		completed
	);
});

test("a rejected timing frame cannot replace the accepted projection", () => {
	const projection = { baseDurationMs: 1000, receivedAtPerformanceMs: 500 };
	const journal = extractActivityJournal([
		{
			type: "data-activities",
			data: {
				activities: [],
				timing: { status: "running", activeDurationMs: 1000 },
				timingProjection: projection,
			},
		},
		{
			type: "data-activities",
			data: {
				activities: [],
				timing: { status: "running", activeDurationMs: 900 },
				timingProjection: { baseDurationMs: 900, receivedAtPerformanceMs: 900 },
			},
		},
	]);

	assert.deepEqual(journal.timing, { status: "running", activeDurationMs: 1000 });
	assert.deepEqual(journal.timingProjection, projection);
});
