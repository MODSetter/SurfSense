import { setIcon } from "obsidian";
import { STATUS_VISUALS } from "./status-visuals";
import type { StatusState } from "./types";

/**
 * Tiny status-bar adornment.
 *
 * Plain DOM (no HTML strings, no CSS-in-JS) so it stays cheap on mobile
 * and Obsidian's lint doesn't complain about innerHTML.
 */

export class StatusBar {
	private readonly el: HTMLElement;
	private readonly icon: HTMLElement;
	private readonly text: HTMLElement;

	constructor(host: HTMLElement, onClick?: () => void) {
		this.el = host;
		this.el.addClass("surfsense-status");
		this.icon = this.el.createSpan({ cls: "surfsense-status__icon" });
		this.text = this.el.createSpan({ cls: "surfsense-status__text" });
		if (onClick) {
			this.el.addClass("surfsense-status--clickable");
			this.el.addEventListener("click", onClick);
		}
		this.update({ kind: "idle", queueDepth: 0 });
	}

	update(state: StatusState): void {
		const visual = STATUS_VISUALS[state.kind];
		this.el.removeClass("surfsense-status--err");
		if (visual.isError) this.el.addClass("surfsense-status--err");
		setIcon(this.icon, visual.icon);

		let label = `SurfSense: ${visual.label}`;
		if (state.queueDepth > 0 && state.kind !== "idle") {
			label += ` (${state.queueDepth})`;
		}
		this.text.setText(label);
		this.el.setAttr(
			"aria-label",
			state.detail ? `${label} — ${state.detail}` : label,
		);
		this.el.setAttr("title", state.detail ?? label);
	}
}
