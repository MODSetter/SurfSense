import assert from "node:assert/strict";
import test from "node:test";

import { reconcileInterruptedAssistantMessages } from "@/lib/chat/message-utils";

interface Message {
	id: number;
	role: "assistant" | "user";
	content: unknown[];
}

const aborted = (id: string, result?: unknown) => ({
	type: "tool-call",
	toolCallId: id,
	toolName: "write_file",
	state: "aborted",
	...(result === undefined ? {} : { result }),
});

const activity = (status: "running" | "completed") => ({
	id: "act-write",
	sequence: 1,
	kind: "file.write",
	status,
	title: status === "completed" ? "Wrote file" : "Writing file",
	category: "file",
	iconKey: "file-plus",
	startedAt: "2026-01-01T00:00:00Z",
	...(status === "completed" ? { completedAt: "2026-01-01T00:00:01Z" } : {}),
});

const journal = (status: "running" | "completed") => ({
	type: "data-activities",
	data: {
		activities: [activity(status)],
		timing: {
			status: status === "completed" ? "completed" : "paused",
			activeDurationMs: status === "completed" ? 800 : 400,
		},
	},
});

test("preserves every stage of a multi-hop interrupt chain in order", () => {
	const messages: Message[] = [
		{
			id: 1,
			role: "assistant",
			content: [journal("running"), { type: "text", text: "first phase" }, aborted("one")],
		},
		{
			id: 2,
			role: "assistant",
			content: [{ type: "reasoning", text: "second phase" }, aborted("two")],
		},
		{
			id: 3,
			role: "assistant",
			content: [{ type: "text", text: "final phase" }],
		},
	];

	const reconciled = reconcileInterruptedAssistantMessages(messages);
	const content = reconciled[0].content as Array<Record<string, unknown>>;

	assert.equal(reconciled.length, 1);
	assert.equal(reconciled[0].id, 3);
	assert.deepEqual(
		content
			.filter((part) => part.type === "text" || part.type === "reasoning")
			.map((part) => part.text),
		["first phase", "second phase", "final phase"]
	);
});

test("preserves text, reasoning, activities, and completed tool results", () => {
	const messages: Message[] = [
		{
			id: 1,
			role: "assistant",
			content: [
				journal("completed"),
				{ type: "text", text: "useful text" },
				{ type: "reasoning", text: "useful reasoning" },
				aborted("one", { status: "completed" }),
			],
		},
		{ id: 2, role: "assistant", content: [{ type: "text", text: "resumed" }] },
	];

	const [reconciled] = reconcileInterruptedAssistantMessages(messages);
	const content = reconciled.content as Array<Record<string, unknown>>;
	const mergedJournal = content.find((part) => part.type === "data-activities") as {
		data: {
			activities: Array<{ status: string }>;
			timing: { status: string; activeDurationMs: number };
		};
	};

	assert.equal(mergedJournal.data.activities[0].status, "completed");
	assert.deepEqual(mergedJournal.data.timing, {
		status: "completed",
		activeDurationMs: 800,
	});
	assert.ok(content.some((part) => part.text === "useful text"));
	assert.ok(content.some((part) => part.text === "useful reasoning"));
	assert.ok(content.some((part) => part.result !== undefined));
});

test("drops only an empty aborted shell when it has a successor", () => {
	const reconciled = reconcileInterruptedAssistantMessages<Message>([
		{ id: 1, role: "assistant", content: [aborted("one")] },
		{ id: 2, role: "assistant", content: [{ type: "text", text: "resumed" }] },
	]);

	assert.deepEqual(
		reconciled.map((message) => message.id),
		[2]
	);
});

test("keeps a never-resumed aborted row", () => {
	const messages: Message[] = [{ id: 1, role: "assistant", content: [aborted("one")] }];

	assert.deepEqual(reconcileInterruptedAssistantMessages(messages), messages);
});

test("does not reconcile across a user-message boundary", () => {
	const messages: Message[] = [
		{ id: 1, role: "assistant", content: [aborted("one")] },
		{ id: 2, role: "user", content: [{ type: "text", text: "new turn" }] },
		{ id: 3, role: "assistant", content: [{ type: "text", text: "answer" }] },
	];

	assert.deepEqual(reconcileInterruptedAssistantMessages(messages), messages);
});

test("terminal activity status wins while successor metadata is retained", () => {
	const reconciled = reconcileInterruptedAssistantMessages<Message>([
		{ id: 1, role: "assistant", content: [journal("completed"), aborted("one")] },
		{
			id: 2,
			role: "assistant",
			content: [journal("running"), { type: "text", text: "done" }],
		},
	]);
	const mergedJournal = (
		reconciled[0].content as Array<{
			type: string;
			data?: { activities: Array<{ status: string }> };
		}>
	).find((part) => part.type === "data-activities");

	assert.equal(reconciled[0].id, 2);
	assert.equal(mergedJournal?.data?.activities[0].status, "completed");
});
