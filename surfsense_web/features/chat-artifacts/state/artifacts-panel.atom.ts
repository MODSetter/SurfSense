import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";
import type { ChatArtifact } from "../model/artifact";

/** Artifacts of the active thread, synced from the message stream by `useSyncChatArtifacts`. */
export const chatArtifactsAtom = atom<ChatArtifact[]>([]);

/** Whether the artifacts sidebar is open in the right panel. */
export const artifactsPanelOpenAtom = atom(false);

/** Snapshot of `rightPanelCollapsedAtom` taken before the panel opens, restored on close. */
const preArtifactsCollapsedAtom = atom<boolean | null>(null);

export const openArtifactsPanelAtom = atom(null, (get, set) => {
	if (!get(artifactsPanelOpenAtom)) {
		set(preArtifactsCollapsedAtom, get(rightPanelCollapsedAtom));
	}
	set(artifactsPanelOpenAtom, true);
	set(rightPanelTabAtom, "artifacts");
	set(rightPanelCollapsedAtom, false);
});

export const closeArtifactsPanelAtom = atom(null, (get, set) => {
	set(artifactsPanelOpenAtom, false);
	set(rightPanelTabAtom, "sources");
	const prev = get(preArtifactsCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preArtifactsCollapsedAtom, null);
	}
});
