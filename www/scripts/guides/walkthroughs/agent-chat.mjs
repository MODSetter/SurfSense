/**
 * Agentic chats for the agent walkthroughs. They run on Claude Haiku 5.5: with
 * Qwen3.8 27B the agent called the analysis tool with nothing to analyse and
 * stopped mid-correction (10 Nov 2026), the stall the plan's fallback is for.
 */

import { join } from "node:path";

import { switchChatModel } from "./chat-model.mjs";
import { startChat } from "./new-chat.mjs";

export const AGENT_MODEL = "anthropic/claude-haiku-5.5";

export function steps(page) {
	return page.getByRole("list", { name: "Steps the agent took" });
}

export function conversation(page) {
	return page.getByRole("region", { name: "Conversation" });
}

export async function switchToAgentModel(g) {
	await switchChatModel(g, AGENT_MODEL);
}

/** Starts an Agentic chat and sends `request`; the shot of its first steps is taken while it works. */
export async function askAgent(g, request, { stepsShot, caption = "Ask for what you want" } = {}) {
	const { page } = g;
	const earlier = await repliesFinished(page);
	await g.type(page.getByRole("textbox", { name: "Message" }), request, { caption, delay: 16 });
	await page.keyboard.press("Enter");
	if (stepsShot) {
		await g.waitFor(() => steps(page).getByRole("listitem").nth(1).waitFor({ timeout: 300_000 }), {
			caption: "The agent works in steps, shown above its reply",
		});
		await g.hold(800);
		await g.shot(stepsShot, { clip: conversation(page), pad: 0 });
	}
	await g.waitFor(() => replyFinished(page, { earlier }), {
		caption: "It reads what it needs, then answers (sped up)",
	});
}

/** How many replies in the open chat have finished: a follow-up waits for one more. */
export async function repliesFinished(page) {
	return page.getByRole("status").filter({ hasText: "Reply finished" }).count();
}

/** Resolves once the chat has more finished replies than `earlier`. */
export async function replyFinished(page, { earlier = 0, timeout = 900_000 } = {}) {
	await page
		.getByRole("status")
		.filter({ hasText: "Reply finished" })
		.nth(earlier)
		.waitFor({ state: "attached", timeout });
}

export async function newAgentChat(g, caption) {
	await startChat(g, "Agentic", { caption: caption ?? "Start a new chat in Agentic mode" });
}

/** Uploads one demo file into Sources and waits until it can be used. */
export async function uploadSource(g, relativePath) {
	const { page } = g;
	const panel = page.getByRole("complementary", { name: "Workspace sources" });
	await panel.getByRole("button", { name: "Add sources" }).click();
	const chooser = page.waitForEvent("filechooser");
	await page.getByRole("menuitem", { name: "Upload files…" }).click();
	await (await chooser).setFiles(join(g.docsDir, relativePath));
	await page.waitForTimeout(1500);
	await panel
		.getByRole("status", { name: /^(Processing|Transcribing)/ })
		.first()
		.waitFor({ state: "detached", timeout: 600_000 });
}

/** Deletes My Workspace's sources with these titles, and what Studio made from them. */
export async function deleteSources(apiUrl, titles) {
	const workspaces = await (await fetch(`${apiUrl}/workspaces`)).json();
	const mine = workspaces.find((workspace) => workspace.name === "My Workspace");
	const documents = await (
		await fetch(`${apiUrl}/workspaces/${mine.id}/documents?document_type=FILE&limit=200`)
	).json();
	for (const document of documents.filter((each) => titles.includes(each.title))) {
		await fetch(`${apiUrl}/workspaces/${mine.id}/documents/${document.id}`, { method: "DELETE" });
	}
}
