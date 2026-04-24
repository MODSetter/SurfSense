import type { StatusKind } from "./types";

/**
 * Single source of truth for status icons + labels. Both the status bar
 * and the settings "Connection" heading render from this table so a change
 * here updates both surfaces.
 */

export interface StatusVisual {
	icon: string;
	label: string;
	isError: boolean;
}

export const STATUS_VISUALS: Record<StatusKind, StatusVisual> = {
	idle: { icon: "check-circle", label: "Synced", isError: false },
	syncing: { icon: "refresh-ccw", label: "Syncing", isError: false },
	queued: { icon: "clock", label: "Queued", isError: false },
	offline: { icon: "wifi-off", label: "Offline", isError: false },
	"auth-error": { icon: "user-x", label: "Reauthenticate", isError: true },
	error: { icon: "alert-circle", label: "Error", isError: true },
};
