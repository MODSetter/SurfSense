import type { StatusKind } from "./types";

/** Shared by the status bar and the settings "Connection" heading. */
export interface StatusVisual {
	icon: string;
	label: string;
	isError: boolean;
}

export const STATUS_VISUALS: Record<StatusKind, StatusVisual> = {
	idle: { icon: "check-circle", label: "Synced", isError: false },
	syncing: { icon: "refresh-ccw", label: "Syncing", isError: false },
	queued: { icon: "clock", label: "Queued", isError: false },
	"needs-setup": { icon: "cloud-off", label: "Setup required", isError: false },
	offline: { icon: "wifi-off", label: "Offline", isError: false },
	"auth-error": { icon: "alert-circle", label: "Reauthenticate", isError: true },
	error: { icon: "alert-circle", label: "Error", isError: true },
};
