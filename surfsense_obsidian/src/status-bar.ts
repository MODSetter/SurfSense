import { setIcon } from "obsidian";
import type { StatusKind, StatusState } from "./types";

/**
 * Tiny status-bar adornment.
 *
 * Plain DOM (no HTML strings, no CSS-in-JS) so it stays cheap on mobile
 * and Obsidian's lint doesn't complain about innerHTML.
 */

interface StatusVisual {
	icon: string;
	label: string;
	cls: string;
}

const VISUALS: Record<StatusKind, StatusVisual> = {
	idle: { icon: "check-circle", label: "Synced", cls: "" },
	syncing: { icon: "refresh-ccw", label: "Syncing", cls: "" },
	queued: { icon: "clock", label: "Queued", cls: "" },
	offline: { icon: "wifi-off", label: "Offline", cls: "" },
	"auth-error": { icon: "user-x", label: "Auth error", cls: "surfsense-status--err" },
	error: { icon: "alert-circle", label: "Error", cls: "surfsense-status--err" },
};

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
		const visual = VISUALS[state.kind];
		this.el.removeClass("surfsense-status--err");
		if (visual.cls) this.el.addClass(visual.cls);
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
