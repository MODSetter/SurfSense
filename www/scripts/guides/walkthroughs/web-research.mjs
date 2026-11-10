/** /docs/v2/guides/web-research: the agent reads a page the user names, after the user allows its site. */

import { askAgent, conversation, newAgentChat, steps, useAgentModel } from "./agent-chat.mjs";
import { closeArtifact } from "./studio.mjs";

const SITE = "www.cisa.gov";
const PAGE = "https://www.cisa.gov/secure-our-world";

export const webResearch = {
	slug: "web-research",
	/** Turns the site off again, so the take shows the question the first visit asks. */
	async prepare({ apiUrl }) {
		const destinations = await (await fetch(`${apiUrl}/egress`)).json();
		const site = destinations.filter((each) => each.host === SITE && each.enabled);
		if (site.length) {
			await fetch(`${apiUrl}/egress`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					destinations: site.map((each) => each.destination),
					enabled: false,
				}),
			});
		}
	},
	async before(g) {
		await closeArtifact(g);
		await useAgentModel(g);
	},
	async run(g) {
		const { page } = g;
		await newAgentChat(g);
		await askAgent(g, `Read ${PAGE} and list the steps it asks everyone to take`, {
			caption: "Name a page, or ask something your sources don’t cover",
		});
		// The agent may also have tried a web search, which offers its own Allow: this one is the page's site.
		const allow = steps(page)
			.getByRole("listitem")
			.filter({ hasText: SITE })
			.getByRole("button", { name: /^Allow/ })
			.or(
				conversation(page).getByRole("button", {
					name: new RegExp(`Allow.*${SITE.replace(/\./g, "\\.")}`),
				})
			)
			.first();
		await allow.waitFor();
		await g.caption("The first time it reaches a site, it asks you to allow it");
		await g.hold(1800);
		await g.shot("allow-site", { clip: conversation(page), pad: 0 });
		await g.click(allow, { caption: "Click Allow" });
		const confirm = page.getByRole("alertdialog");
		if (await confirm.isVisible().catch(() => false)) {
			await g.click(confirm.getByRole("button", { name: "Allow" }));
		}
		await g.hold(800);
		await askAgent(g, "Allowed. Please read it now.", { caption: "Then ask again" });
		await g.hold(1800);
		await g.shot("answer", { clip: conversation(page), pad: 0 });
	},
};
