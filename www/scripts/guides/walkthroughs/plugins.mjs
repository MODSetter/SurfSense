/**
 * /docs/v2/guides/plugins: add DeepWiki's public MCP server by its URL, read
 * its tools, then approve its use in an Agentic chat. DeepWiki needs no
 * sign-in, and its tools always ask first, which shows the approval.
 */

import { conversation, newAgentChat, replyFinished, switchToAgentModel } from "./agent-chat.mjs";
import { setHostAllowed } from "./egress.mjs";
import { closeSettings, openSettingsSection } from "./open-settings.mjs";
import { closeArtifact } from "./studio.mjs";

const NAME = "DeepWiki";
const SERVER_URL = "https://mcp.deepwiki.com/mcp";

export const plugins = {
	slug: "plugins",
	/** Removes an earlier take's server and turns third-party plugins off, as on a new install. */
	async prepare({ apiUrl }) {
		const all = await (await fetch(`${apiUrl}/plugins`)).json();
		for (const plugin of all.filter((each) => each.name === NAME)) {
			await fetch(`${apiUrl}/plugins/${plugin.id}`, { method: "DELETE" });
		}
		await fetch(`${apiUrl}/plugins/third-party`, {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ allowed: false }),
		});
		await setHostAllowed(apiUrl, "mcp.deepwiki.com", false);
	},
	async before(g) {
		await closeArtifact(g);
		await switchToAgentModel(g);
	},
	async run(g) {
		const { page } = g;
		const settings = await openSettingsSection(g, "Plugins", {
			caption: "Open Settings, then Plugins",
		});
		await g.click(settings.getByRole("button", { name: "Add custom plugin" }).first(), {
			caption: "Click Add custom plugin to add a server by its URL",
		});
		const form = page.getByRole("dialog", { name: "Add an MCP server" });
		await g.click(form.getByRole("switch", { name: "Allow third-party plugins" }), {
			caption: "Allow third-party plugins first",
		});
		const thirdParty = page.getByRole("alertdialog", { name: "Allow third-party plugins?" });
		await thirdParty.waitFor();
		await g.hold(1500);
		await g.shot("allow-third-party", { clip: thirdParty });
		await g.click(thirdParty.getByRole("button", { name: "Allow" }));
		await g.type(form.getByRole("textbox", { name: "Name" }), NAME, { caption: "Name it" });
		await g.type(form.getByRole("textbox", { name: "Server URL" }), SERVER_URL, {
			caption: "Paste its URL",
			delay: 12,
		});
		await g.shot("add-server", { clip: form });
		await g.click(form.getByRole("button", { name: "Add" }), { caption: "Click Add" });
		const host = page.getByRole("alertdialog");
		await host.waitFor();
		await g.caption("SurfSense asks before it contacts the server");
		await g.hold(1500);
		await g.shot("allow-server", { clip: host });
		await g.click(host.getByRole("button", { name: "Allow" }));
		// SurfSense opens the new plugin's page; an older build listed it under Yours first.
		const connected = settings.getByText("Connected");
		const row = settings.getByRole("button", { name: NAME, exact: true });
		await g.waitFor(() => connected.or(row).first().waitFor({ timeout: 60_000 }), {
			caption: "It lists the server’s tools",
		});
		if (!(await connected.count())) await g.click(row, { caption: "Open it to see its tools" });
		await connected.waitFor();
		await g.caption("Choose what each tool may do");
		await g.hold(1800);
		await g.shot("tools", { clip: settings });
		await closeSettings(g);

		await newAgentChat(g);
		await g.type(
			page.getByRole("textbox", { name: "Message" }),
			"Use DeepWiki to tell me in a few lines what the OWASP/CheatSheetSeries repository covers",
			{
				caption: "In an Agentic chat, ask for something the plugin does",
				delay: 16,
			}
		);
		await page.keyboard.press("Enter");
		const allowOnce = page.getByRole("button", { name: /Allow once/ }).first();
		await g.waitFor(() => allowOnce.waitFor({ timeout: 300_000 }), {
			caption: "The agent picks the tool (sped up)",
		});
		await g.caption("A tool that needs approval asks first, with what it will send");
		await g.hold(1800);
		await g.shot("approval", { clip: conversation(page), pad: 0 });
		await g.click(allowOnce, { caption: "Click Allow once, or Deny" });
		await g.waitFor(
			async () => {
				for (let round = 0; round < 6; round++) {
					const again = page.getByRole("button", { name: /Allow once/ });
					await Promise.race([
						again.first().waitFor({ timeout: 300_000 }),
						replyFinished(page, { timeout: 300_000 }),
					]);
					if (await page.getByRole("status").filter({ hasText: "Reply finished" }).count()) return;
					await again.first().click();
				}
			},
			{ caption: "The answer comes from the plugin’s tool (sped up)" }
		);
		await g.hold(1800);
		await g.shot("answer", { clip: conversation(page), pad: 0 });
	},
};
