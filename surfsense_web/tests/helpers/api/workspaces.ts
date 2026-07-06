import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type SearchSpaceRow = {
	id: number;
	name: string;
	description: string | null;
};

export async function createSearchSpace(
	request: APIRequestContext,
	token: string,
	name: string,
	description = "E2E test search space"
): Promise<SearchSpaceRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/workspaces`, {
		headers: authHeaders(token),
		data: { name, description },
	});
	if (!response.ok()) {
		throw new Error(`createSearchSpace failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as SearchSpaceRow;
}

export async function deleteSearchSpace(
	request: APIRequestContext,
	token: string,
	id: number
): Promise<void> {
	const response = await request.delete(`${BACKEND_URL}/api/v1/workspaces/${id}`, {
		headers: authHeaders(token),
	});
	if (!response.ok() && response.status() !== 404) {
		// 404 is acceptable: the test may have already deleted the space.
		throw new Error(
			`deleteSearchSpace(${id}) failed (${response.status()}): ${await response.text()}`
		);
	}
}
