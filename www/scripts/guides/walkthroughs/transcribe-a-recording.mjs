/**
 * /docs/v2/guides/transcribe-a-recording: download a speech recognition model,
 * add a recording, and ask about it. Canary 180M Flash: the lighter of the two,
 * and enough for an English reading.
 */

import { join } from "node:path";

import { deleteSources } from "./agent-chat.mjs";
import { ask, startChat } from "./new-chat.mjs";
import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { closeArtifact } from "./studio.mjs";

const RECORDING = "The Art of War, chapters 1 and 2.mp3";
const MODEL = "Canary 180M Flash Q8_0";

export const transcribeARecording = {
	slug: "transcribe-a-recording",
	/** Deletes an earlier take's recording and speech model, so the take downloads and transcribes again. */
	async prepare({ apiUrl }) {
		await deleteSources(apiUrl, [RECORDING]);
		const catalog = await (await fetch(`${apiUrl}/llm/catalog/local`)).json();
		const rows = Array.isArray(catalog) ? catalog : (catalog.rows ?? catalog.models ?? []);
		for (const row of rows.filter((each) => each.transcription)) {
			for (const build of row.builds ?? []) {
				if (build.installed_as) {
					await fetch(`${apiUrl}/llm/models/${encodeURIComponent(build.installed_as)}`, {
						method: "DELETE",
					});
				}
			}
		}
	},
	async before(g) {
		await closeArtifact(g);
	},
	async run(g) {
		const { page } = g;
		const settings = await openSettingsSection(g, "Speech recognition", {
			caption: "Open Settings, then Speech recognition",
		});
		await g.click(settings.getByRole("button", { name: "Add model" }), {
			caption: "Click Add model",
		});
		const download = settings.getByRole("button", { name: `Download ${MODEL}` });
		await download.waitFor();
		await g.hold(1200);
		await g.shot("speech-models", { clip: settings });
		await g.click(download, { caption: "Download a model: it runs on this computer" });
		await g.waitFor(() => settings.getByText("In use").first().waitFor({ timeout: 600_000 }), {
			caption: "Downloading a model also chooses it (sped up)",
		});
		await g.hold(1200);
		await closeSettings(g);

		const panel = page.getByRole("complementary", { name: "Workspace sources" });
		await g.click(panel.getByRole("button", { name: "Add sources" }), {
			caption: "Add a recording like any file",
		});
		const chooser = page.waitForEvent("filechooser");
		await g.click(page.getByRole("menuitem", { name: "Upload files…" }));
		await (await chooser).setFiles(join(g.docsDir, "Recordings", RECORDING));
		const row = panel.getByRole("treeitem", { name: RECORDING });
		await row.getByText(/Transcribing/).waitFor({ timeout: 120_000 });
		await g.caption("Its row shows how far the transcript has got");
		await g.hold(1500);
		await g.shot("transcribing", {
			clip: [panel.getByRole("heading", { name: "Sources" }), row],
			pad: 16,
		});
		await g.waitFor(
			() => row.getByText(/Transcribing/).waitFor({ state: "detached", timeout: 900_000 }),
			{ caption: "It’s transcribed on this computer (sped up)" }
		);

		await startChat(g, "Basic (Q&A)");
		await ask(
			g,
			"According to the recording, what five factors should be weighed before going to war?"
		);
		const conversation = page.getByRole("region", { name: "Conversation" });
		await g.hold(1500);
		await g.click(conversation.getByRole("button", { name: /^View cited chunk/ }).first(), {
			caption: "A cited passage says when in the recording it was said",
		});
		await page.getByRole("complementary", { name: "Citation" }).waitFor();
		await g.hold(1800);
		await g.shot("cited-recording");
	},
};
