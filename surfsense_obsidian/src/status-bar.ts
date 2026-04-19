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
	idle: { icon: "check-circle", label: "Synced", cls: "surfsense-status--ok" },
	syncing: { icon: "refresh-ccw", label: "Syncing", cls: "surfsense-status--syncing" },
	queued: { icon: "upload", label: "Queued", cls: "surfsense-status--syncing" },
	offline: { icon: "wifi-off", label: "Offline", cls: "surfsense-status--warn" },
	"auth-error": { icon: "lock", label: "Auth error", cls: "surfsense-status--err" },
	error: { icon: "alert-circle", label: "Error", cls: "surfsense-status--err" },
};

export class StatusBar {
	private readonly el: HTMLElement;
	private readonly icon: HTMLElement;
	private readonly text: HTMLElement;

	constructor(host: HTMLElement) {
		this.el = host;
		this.el.addClass("surfsense-status");
		this.icon = this.el.createSpan({ cls: "surfsense-status__icon" });
		this.text = this.el.createSpan({ cls: "surfsense-status__text" });
		this.update({ kind: "idle", queueDepth: 0 });
	}

	update(state: StatusState): void {
		const visual = VISUALS[state.kind];
		this.el.removeClass(
			"surfsense-status--ok",
			"surfsense-status--syncing",
			"surfsense-status--warn",
			"surfsense-status--err",
		);
		this.el.addClass(visual.cls);
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
