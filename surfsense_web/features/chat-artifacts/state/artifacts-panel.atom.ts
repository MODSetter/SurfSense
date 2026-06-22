import { atom } from "jotai";
import type { ChatArtifact } from "../model/artifact";

/** Artifacts of the active thread, synced from the message stream by `useSyncChatArtifacts`. */
export const chatArtifactsAtom = atom<ChatArtifact[]>([]);

/** Whether the artifacts sidebar is open in the right panel. */
export const artifactsPanelOpenAtom = atom(false);
