import path from "node:path";
import type { APIRequestContext, Page } from "@playwright/test";
import { expect, manualUploadWithChatTest as test } from "../../fixtures";
import type { ChatThreadRow } from "../../fixtures/chat-thread.fixture";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { getEditorContent, listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS } from "../../helpers/canary";
import { waitForDocumentByTitle } from "../../helpers/waits/indexing";

type UploadFixture = {
	path: string;
	name: string;
	canary: string;
	chatQuery: string;
};

type SearchSpace = {
	id: number;
};

const MD_FILE: UploadFixture = {
	path: path.join(__dirname, "fixtures", "canary.md"),
	name: "canary.md",
	canary: CANARY_TOKENS.manualUploadMdCanary,
	chatQuery: "What is in my uploaded canary.md markdown file?",
};

const PDF_FILE: UploadFixture = {
	path: path.join(__dirname, "fixtures", "canary.pdf"),
	name: "canary.pdf",
	canary: CANARY_TOKENS.manualUploadPdfCanary,
	chatQuery: "What is in my uploaded canary.pdf file?",
};

async function uploadAndAssert({
	page,
	request,
	apiToken,
	searchSpace,
	chatThread,
	file,
}: {
	page: Page;
	request: APIRequestContext;
	apiToken: string;
	searchSpace: SearchSpace;
	chatThread: ChatThreadRow;
	file: UploadFixture;
}) {
	await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
		waitUntil: "domcontentloaded",
	});

	await page.getByRole("button", { name: "Upload" }).click();
	const dialog = page.getByRole("dialog", { name: "Upload Documents" });
	await expect(dialog).toBeVisible();

	await dialog.locator('input[type="file"]').first().setInputFiles(file.path);
	await dialog.getByRole("button", { name: /Upload 1 file/i }).click();

	await expect(page.getByText(/Upload Task Initiated/i)).toBeVisible({
		timeout: 15_000,
	});

	await waitForDocumentByTitle(request, apiToken, searchSpace.id, file.name, {
		timeoutMs: 200_000,
	});

	const docs = await listDocuments(request, apiToken, searchSpace.id);
	const uploaded = docs.find((d) => d.title === file.name);
	expect(uploaded, `${file.name} must exist after indexing`).toBeDefined();
	if (!uploaded) throw new Error("unreachable: uploaded asserted defined above");
	expect(uploaded.document_type).toBe("FILE");

	const editor = await getEditorContent(request, apiToken, searchSpace.id, uploaded.id);
	expect(editor.source_markdown).toContain(file.canary);
	expect(editor.chunk_count).toBeGreaterThan(0);

	const chat = await streamChatToCompletion(request, apiToken, {
		searchSpaceId: searchSpace.id,
		threadId: chatThread.id,
		query: file.chatQuery,
	});
	expect(
		chat.assistantText,
		`chat agent should surface manual upload canary after indexing; got: ${chat.assistantText.slice(0, 200)}`
	).toContain(file.canary);
}

test.describe("Manual file upload journey", () => {
	test("user uploads a markdown file (PLAINTEXT branch)", async ({
		page,
		request,
		apiToken,
		searchSpace,
		chatThread,
	}) => {
		test.setTimeout(180_000);

		await uploadAndAssert({
			page,
			request,
			apiToken,
			searchSpace,
			chatThread,
			file: MD_FILE,
		});
	});

	test("user uploads a PDF (DOCUMENT branch)", async ({
		page,
		request,
		apiToken,
		searchSpace,
		chatThread,
	}) => {
		test.setTimeout(180_000);

		await uploadAndAssert({
			page,
			request,
			apiToken,
			searchSpace,
			chatThread,
			file: PDF_FILE,
		});
	});
});
