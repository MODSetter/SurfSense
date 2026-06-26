export { useSyncChatArtifacts } from "./hooks/use-sync-chat-artifacts";
export { collectArtifacts } from "./lib/collect-artifacts";
export { ARTIFACT_ANCHOR_ATTR, scrollToArtifact } from "./lib/scroll-to-artifact";
export type { ArtifactKind, ArtifactStatus, ChatArtifact } from "./model/artifact";
export {
	artifactsPanelOpenAtom,
	chatArtifactsAtom,
	closeArtifactsPanelAtom,
	openArtifactsPanelAtom,
	toggleArtifactsPanelAtom,
} from "./state/artifacts-panel.atom";
export { withArtifactAnchor } from "./ui/artifact-anchor";
export { ArtifactsPanelContent, MobileArtifactsPanel } from "./ui/artifacts-panel";
export { ArtifactsToggleButton } from "./ui/artifacts-toggle-button";
