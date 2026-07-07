import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type ChatStreamEvent = {
	type: string;
	payload: unknown;
};

export type ChatStreamResult = {
	assistantText: string;
	events: ChatStreamEvent[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function streamChatToCompletion(
	request: APIRequestContext,
	token: string,
	args: { workspaceId: number; threadId: number; query: string }
): Promise<ChatStreamResult> {
	const response = await request.post(`${BACKEND_URL}/api/v1/new_chat`, {
		headers: authHeaders(token),
		data: {
			chat_id: args.threadId,
			workspace_id: args.workspaceId,
			user_query: args.query,
		},
	});
	if (!response.ok()) {
		throw new Error(
			`streamChatToCompletion failed (${response.status()}): ${await response.text()}`
		);
	}

	const body = await response.text();
	let assistantText = "";
	let sawDone = false;
	const events: ChatStreamEvent[] = [];

	for (const rawFrame of body.split("\n\n")) {
		const frame = rawFrame.trim();
		if (!frame) continue;
		if (!frame.startsWith("data: ")) continue;

		const payloadText = frame.slice("data: ".length);
		if (payloadText === "[DONE]") {
			sawDone = true;
			events.push({ type: "done", payload: "[DONE]" });
			break;
		}

		const payload = JSON.parse(payloadText) as unknown;
		const type = isRecord(payload) && typeof payload.type === "string" ? payload.type : "unknown";
		if (type === "text-delta" && isRecord(payload) && typeof payload.delta === "string") {
			assistantText += payload.delta;
		}
		events.push({ type, payload });
	}

	if (!sawDone) {
		throw new Error(`Chat stream did not finish with [DONE]. Body: ${body.slice(0, 500)}`);
	}

	return { assistantText, events };
}
