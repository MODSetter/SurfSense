import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";
import type { SearchSpaceFixtures } from "./search-space.fixture";

export type ChatThreadRow = {
	id: number;
	title: string;
	search_space_id: number;
	visibility: string;
	created_by_id: string | null;
	created_at: string;
	updated_at: string;
};

export type ChatThreadFixtures = {
	chatThread: ChatThreadRow;
};

type ChatThreadFixtureArgs = SearchSpaceFixtures & {
	request: APIRequestContext;
};

export const chatThreadFixtures = {
	chatThread: async (
		{ request, apiToken, searchSpace }: ChatThreadFixtureArgs,
		use: (thread: ChatThreadRow) => Promise<void>
	) => {
		const response = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-drive-journey",
				workspace_id: searchSpace.id,
				visibility: "PRIVATE",
			},
		});
		if (!response.ok()) {
			throw new Error(`create chat thread failed (${response.status()}): ${await response.text()}`);
		}

		await use((await response.json()) as ChatThreadRow);
	},
};
