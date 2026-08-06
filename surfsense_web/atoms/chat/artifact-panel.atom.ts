import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface ArtifactPanelState {
	isOpen: boolean;
	documentId: number | null;
}

const initialState: ArtifactPanelState = {
	isOpen: false,
	documentId: null,
};

export const artifactPanelAtom = atom<ArtifactPanelState>(initialState);
const preArtifactCollapsedAtom = atom<boolean | null>(null);

export const openArtifactPanelAtom = atom(
	null,
	(get, set, { documentId }: { documentId: number }) => {
		if (!get(artifactPanelAtom).isOpen) {
			set(preArtifactCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		set(artifactPanelAtom, { isOpen: true, documentId });
		set(rightPanelTabAtom, "artifact");
		set(rightPanelCollapsedAtom, false);
	}
);

export const closeArtifactPanelAtom = atom(null, (get, set) => {
	set(artifactPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const previous = get(preArtifactCollapsedAtom);
	if (previous !== null) {
		set(rightPanelCollapsedAtom, previous);
		set(preArtifactCollapsedAtom, null);
	}
});
