import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export type RightPanelTab =
	| "sources"
	| "report"
	| "editor"
	| "hitl-edit"
	| "citation"
	| "artifacts";

export const rightPanelTabAtom = atom<RightPanelTab>("sources");

/** Whether the right panel is collapsed (hidden but state preserved) */
export const rightPanelCollapsedAtom = atomWithStorage("right-panel-collapsed:v1", false);
