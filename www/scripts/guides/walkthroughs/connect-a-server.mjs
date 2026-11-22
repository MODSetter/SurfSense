/**
 * /docs/v2/guides/connect-a-server: OpenRouter in Settings › Text gen, then a
 * model from it. The key field gets a placeholder, and the request that saves the
 * server carries the real key from `OPENROUTER_API_KEY` instead, so no real key
 * is typed or shown.
 */

import { setHostAllowed } from "./egress.mjs";
import { closeSettings, openSettingsSection } from "./open-settings.mjs";

const PLACEHOLDER_KEY = "sk-or-v1-placeholder-for-the-guides-0000000000000000000000000000000";
const MODEL = "qwen/qwen3.8-27b";

export const connectAServer = {
	slug: "connect-a-server",
	/** A retake would otherwise add a second server beside the first take's, and skip the question about the host. */
	async prepare({ apiUrl }) {
		const connections = await (await fetch(`${apiUrl}/llm/connections`)).json();
		for (const connection of connections.filter((each) =>
			each.base_url?.includes("openrouter.ai")
		)) {
			await fetch(`${apiUrl}/llm/connections/${connection.id}`, { method: "DELETE" });
		}
		await setHostAllowed(apiUrl, "openrouter.ai", false);
	},
	async run(g) {
		const { page } = g;
		const key = process.env.OPENROUTER_API_KEY;
		if (!key) throw new Error("connect-a-server needs OPENROUTER_API_KEY");
		await page.route("**/llm/connections", async (route) => {
			const request = route.request();
			const body = request.method() === "POST" ? JSON.parse(request.postData() ?? "{}") : null;
			if (body?.api_key !== PLACEHOLDER_KEY) return route.continue();
			await route.continue({ postData: JSON.stringify({ ...body, api_key: key }) });
		});

		const settings = await openSettingsSection(g, "Text gen", {
			caption: "Open Settings, then Text gen",
		});
		await g.click(settings.getByRole("button", { name: "Add model" }), {
			caption: "Click Add model",
		});
		const server = settings.getByRole("region", { name: "Use a server" });
		await g.click(server.getByRole("button", { name: "Connect" }), {
			caption: "Under Use a server, click Connect",
		});

		const form = page.getByRole("dialog", { name: "Connect a server" });
		await form.waitFor();
		await g.click(form.getByRole("combobox", { name: "Provider" }), {
			caption: "Pick your provider",
		});
		await page.keyboard.type("OpenRouter", { delay: 60 });
		await g.hold(700);
		await g.shot("provider", { clip: [form, page.getByRole("listbox")] });
		await g.click(page.getByRole("option", { name: /^OpenRouter/ }));
		await g.caption("The provider fills in the name and the base URL");
		await g.point(form.getByRole("textbox", { name: "Base URL" }));
		await g.hold(900);
		await g.type(form.getByRole("textbox", { name: "API key" }), PLACEHOLDER_KEY, {
			caption: "Paste your API key",
			delay: 8,
		});
		await g.hold(600);
		await g.shot("server-form", { clip: form });
		await g.click(form.getByRole("button", { name: "Save server" }), {
			caption: "Click Save server",
		});
		// Asked only the first time: a retake on an install that allowed the host goes straight on.
		const ask = page.getByRole("alertdialog");
		await Promise.race([ask.waitFor(), form.waitFor({ state: "detached" })]);
		if (await ask.count()) {
			await g.caption("SurfSense asks before it sends anything to the server");
			await g.hold(1400);
			await g.shot("allow-server", { clip: ask });
			await g.click(ask.getByRole("button", { name: "Allow" }));
		}
		await g.waitFor(() => form.waitFor({ state: "detached", timeout: 60_000 }), {
			caption: "SurfSense checks the server and lists its models",
		});

		const search = settings.getByPlaceholder("Search chat models");
		await g.type(search, "qwen3.8", { caption: "Find a model" });
		await g.hold(800);
		await g.shot("server-models", { clip: settings });
		await g.click(settings.getByRole("button", { name: `Use ${MODEL}`, exact: true }), {
			caption: "Click Use",
		});

		const confirm = page.getByRole("dialog", { name: `Use ${MODEL} for chat?` });
		await confirm.waitFor();
		await g.click(confirm.getByRole("button", { name: "Test chat" }), {
			caption: "Test chat sends one short prompt",
		});
		await g.waitFor(
			() => confirm.getByRole("button", { name: "Use this model" }).waitFor({ timeout: 120_000 }),
			{
				caption: "The model answers the test",
			}
		);
		await g.hold(1000);
		await g.shot("test-chat", { clip: confirm });
		await g.click(confirm.getByRole("button", { name: "Use this model" }), {
			caption: "Click Use this model",
		});
		await g.hold(1200);
		await g.shot("in-use", {
			clip: settings.getByRole("region", { name: "chat model in use" }),
			pad: 20,
		});
		await closeSettings(g);
		await page.unroute("**/llm/connections");
	},
};
