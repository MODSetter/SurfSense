import { atom } from "jotai";

export type RightPanelTab = "sources" | "report" | "editor" | "hitl-edit" | "citation";

export const rightPanelTabAtom = atom<RightPanelTab>("sources");

/** Whether the right panel is collapsed (hidden but state preserved) */
export const rightPanelCollapsedAtom = atom(false);
