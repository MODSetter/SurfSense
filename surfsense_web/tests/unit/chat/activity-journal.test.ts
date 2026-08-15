import assert from "node:assert/strict";
import test from "node:test";

import { extractActivityJournal, parseActivityJournalPart } from "@/lib/chat/activity-journal";

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
