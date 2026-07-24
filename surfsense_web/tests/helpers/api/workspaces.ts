import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type WorkspaceRow = {
	id: number;
	name: string;
	description: string | null;
};

export async function createWorkspace(
	request: APIRequestContext,
	token: string,
	name: string,
	description = "E2E test workspace"
): Promise<WorkspaceRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/workspaces`, {
		headers: authHeaders(token),
		data: { name, description },
	});
	if (!response.ok()) {
		throw new Error(`createWorkspace failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as WorkspaceRow;
}

export async function deleteWorkspace(
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
			`deleteWorkspace(${id}) failed (${response.status()}): ${await response.text()}`
		);
	}
}
