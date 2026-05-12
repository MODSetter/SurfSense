import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { streamChatToCompletion } from "../helpers/api/chat";

test.describe("Smoke", () => {
	test("chat stream completes for an unrelated query", async ({
		request,
		apiToken,
		searchSpace,
	}) => {
		const threadResponse = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-chat-stream-smoke",
				search_space_id: searchSpace.id,
				visibility: "PRIVATE",
			},
		});
		expect(threadResponse.ok()).toBeTruthy();

		const thread = (await threadResponse.json()) as { id: number };
		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: thread.id,
			query: "E2E_NO_RELEVANT_CONTENT_SMOKE",
		});

		expect(chat.events.some((event) => event.type === "done")).toBeTruthy();
		expect(chat.events.some((event) => event.type === "text-delta")).toBeTruthy();
		expect(chat.assistantText).toContain("No relevant indexed content found.");
	});
});
