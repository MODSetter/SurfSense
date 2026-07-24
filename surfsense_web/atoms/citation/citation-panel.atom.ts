import { atom, type Getter, type Setter } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

/** The source the citation panel is showing: a KB chunk or a scraper run. */
export type CitationTarget =
	| { kind: "chunk"; chunkId: number }
	| { kind: "run"; runId: string };

interface CitationPanelState {
	isOpen: boolean;
	target: CitationTarget | null;
}

const initialState: CitationPanelState = {
	isOpen: false,
	target: null,
};

export const citationPanelAtom = atom<CitationPanelState>(initialState);

export const citationPanelOpenAtom = atom((get) => get(citationPanelAtom).isOpen);

const preCitationCollapsedAtom = atom<boolean | null>(null);

function openWithTarget(get: Getter, set: Setter, target: CitationTarget) {
	if (!get(citationPanelAtom).isOpen) {
		set(preCitationCollapsedAtom, get(rightPanelCollapsedAtom));
	}
	set(citationPanelAtom, { isOpen: true, target });
	set(rightPanelTabAtom, "citation");
	set(rightPanelCollapsedAtom, false);
}

export const openCitationPanelAtom = atom(null, (get, set, payload: { chunkId: number }) => {
	openWithTarget(get, set, { kind: "chunk", chunkId: payload.chunkId });
});

export const openRunCitationPanelAtom = atom(null, (get, set, payload: { runId: string }) => {
	openWithTarget(get, set, { kind: "run", runId: payload.runId });
});

export const closeCitationPanelAtom = atom(null, (get, set) => {
	set(citationPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preCitationCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preCitationCollapsedAtom, null);
	}
});
