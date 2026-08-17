import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { appendThreadMessage } from "../helpers/api/chat";

const activity = (status: "awaiting_approval" | "completed", id: string) => ({
	id,
	sequence: 1,
	kind: "memory.team",
	status,
	title: status === "completed" ? "Updated team memory" : "Updating team memory",
	category: "action",
	iconKey: "brain",
	startedAt: "2026-01-01T00:00:00Z",
	...(status === "completed" ? { completedAt: "2026-01-01T00:00:02Z" } : {}),
});

const journal = (
	status: "awaiting_approval" | "completed",
	activeDurationMs: number,
	activityId: string
) => ({
	type: "data-activities",
	data: {
		activities: [activity(status, activityId)],
		timing: {
			status: status === "completed" ? "completed" : "paused",
			activeDurationMs,
		},
	},
});

const interruptedTool = (id: string, activityId: string) => ({
	type: "tool-call",
	toolCallId: id,
	toolName: "update_memory",
	args: {},
	state: "aborted",
	metadata: { activityId },
});

const completedTiming = (activeDurationMs: number) => ({
	type: "data-activities",
	data: {
		activities: [],
		timing: { status: "completed", activeDurationMs },
	},
});

test.describe("Smoke", () => {
	test("completed no-trace turn retains its responded timing", async ({
		page,
		request,
		apiToken,
		workspace,
	}) => {
		const threadResponse = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-no-trace-turn-timing",
				workspace_id: workspace.id,
				visibility: "PRIVATE",
			},
		});
		expect(threadResponse.ok()).toBeTruthy();
		const thread = (await threadResponse.json()) as { id: number };

		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "user",
			turnId: "e2e-no-trace-user",
			content: [{ type: "text", text: "Give me a short answer" }],
		});
		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "assistant",
			turnId: "e2e-no-trace-assistant",
			content: [completedTiming(1600), { type: "text", text: "This answer has no trace segment." }],
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread.id}`);

		const assistantTurn = page.locator('[data-role="assistant"]');
		await expect(assistantTurn).toHaveCount(1, { timeout: 60_000 });
		const header = assistantTurn.getByTestId("assistant-standalone-turn-header");
		await expect(header).toHaveCount(1);
		await expect(header.getByText("Responded", { exact: true })).toBeVisible();
		await expect(header.getByTestId("assistant-turn-timing")).toContainText("1.6s");

		await page.reload();
		const reloadedHeader = page
			.locator('[data-role="assistant"]')
			.getByTestId("assistant-standalone-turn-header");
		await expect(reloadedHeader).toHaveCount(1, { timeout: 60_000 });
		await expect(reloadedHeader.getByText("Responded", { exact: true })).toBeVisible();
		await expect(reloadedHeader.getByTestId("assistant-turn-timing")).toContainText("1.6s");
	});

	test("reload reconciles a three-stage interrupted assistant turn", async ({
		page,
		request,
		apiToken,
		workspace,
	}) => {
		const threadResponse = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-interrupt-reconcile",
				workspace_id: workspace.id,
				visibility: "PRIVATE",
			},
		});
		expect(threadResponse.ok()).toBeTruthy();
		const thread = (await threadResponse.json()) as { id: number };

		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "user",
			turnId: "e2e-user-turn",
			content: [{ type: "text", text: "Remember this preference" }],
		});
		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "assistant",
			turnId: "e2e-paused-one",
			content: [
				journal("awaiting_approval", 400, "act-memory-one"),
				interruptedTool("call-one", "act-memory-one"),
				{ type: "text", text: "First phase survived." },
			],
		});
		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "assistant",
			turnId: "e2e-paused-two",
			content: [
				journal("completed", 2400, "act-memory-two"),
				interruptedTool("call-two", "act-memory-two"),
				{ type: "text", text: "Second phase survived." },
			],
		});
		await appendThreadMessage(request, apiToken, {
			threadId: thread.id,
			role: "assistant",
			turnId: "e2e-resumed-final",
			content: [{ type: "text", text: "Final phase survived." }],
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread.id}`);

		const assistantTurn = page.locator('[data-role="assistant"]');
		await expect(assistantTurn).toHaveCount(1, { timeout: 60_000 });
		await expect(assistantTurn.getByText("First phase survived.")).toBeVisible();
		await expect(assistantTurn.getByText("Second phase survived.")).toBeVisible();
		await expect(assistantTurn.getByText("Final phase survived.")).toBeVisible();
		const timer = assistantTurn.getByTestId("assistant-turn-timing");
		await expect(timer).toHaveCount(1);
		await expect(timer).toContainText("2.4s");
		await expect(
			assistantTurn.getByRole("button", {
				name: "Updating team memory",
				exact: true,
			})
		).not.toContainText("2.4s");
		await expect(
			assistantTurn.getByRole("button", {
				name: "Updated team memory 2.4s",
				exact: true,
			})
		).toBeVisible();

		await page.reload();
		const reloadedAssistantTurn = page.locator('[data-role="assistant"]');
		await expect(reloadedAssistantTurn).toHaveCount(1, {
			timeout: 60_000,
		});
		await expect(reloadedAssistantTurn.getByText("First phase survived.")).toBeVisible();
		await expect(reloadedAssistantTurn.getByText("Second phase survived.")).toBeVisible();
		await expect(reloadedAssistantTurn.getByText("Final phase survived.")).toBeVisible();
		const reloadedTimer = reloadedAssistantTurn.getByTestId("assistant-turn-timing");
		await expect(reloadedTimer).toHaveCount(1);
		await expect(reloadedTimer).toContainText("2.4s");
		await expect(
			reloadedAssistantTurn.getByRole("button", {
				name: "Updating team memory",
				exact: true,
			})
		).not.toContainText("2.4s");
		await expect(
			reloadedAssistantTurn.getByRole("button", {
				name: "Updated team memory 2.4s",
				exact: true,
			})
		).toBeVisible();
	});
});
