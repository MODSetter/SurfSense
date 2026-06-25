import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";
import type { ChatArtifact } from "../model/artifact";

/** Artifacts of the active thread, synced from the message stream by `useSyncChatArtifacts`. */
export const chatArtifactsAtom = atom<ChatArtifact[]>([]);

/** Open === artifacts owns the tab; derived so the toggle can't drift. */
export const artifactsPanelOpenAtom = atom((get) => get(rightPanelTabAtom) === "artifacts");

/** Snapshot of `rightPanelCollapsedAtom` taken before the panel opens, restored on close. */
const preArtifactsCollapsedAtom = atom<boolean | null>(null);

export const openArtifactsPanelAtom = atom(null, (get, set) => {
	if (get(rightPanelTabAtom) !== "artifacts") {
		set(preArtifactsCollapsedAtom, get(rightPanelCollapsedAtom));
	}
	set(rightPanelTabAtom, "artifacts");
	set(rightPanelCollapsedAtom, false);
});

export const closeArtifactsPanelAtom = atom(null, (get, set) => {
	// Don't clobber the tab when another surface owns it.
	if (get(rightPanelTabAtom) !== "artifacts") return;
	// RightPanel's fallback then re-reveals any surface underneath (e.g. a report).
	set(rightPanelTabAtom, "sources");
	const prev = get(preArtifactsCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preArtifactsCollapsedAtom, null);
	}
});

export const toggleArtifactsPanelAtom = atom(null, (get, set) => {
	// Only close when artifacts is actually visible; otherwise a click always opens it.
	const shown = get(rightPanelTabAtom) === "artifacts" && !get(rightPanelCollapsedAtom);
	if (shown) set(closeArtifactsPanelAtom);
	else set(openArtifactsPanelAtom);
});
