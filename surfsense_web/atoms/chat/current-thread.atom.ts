import { atom } from "jotai";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";
import { reportPanelAtom } from "./report-panel.atom";

interface CurrentThreadState {
	id: number | null;
	visibility: ChatVisibility | null;
	hasComments: boolean;
}

const initialState: CurrentThreadState = {
	id: null,
	visibility: null,
	hasComments: false,
};

export const currentThreadAtom = atom<CurrentThreadState>(initialState);

export const commentsEnabledAtom = atom(
	(get) => get(currentThreadAtom).visibility === "SEARCH_SPACE"
);

export const setThreadVisibilityAtom = atom(null, (get, set, newVisibility: ChatVisibility) => {
	set(currentThreadAtom, { ...get(currentThreadAtom), visibility: newVisibility });
});

export const resetCurrentThreadAtom = atom(null, (_, set) => {
	set(currentThreadAtom, initialState);
	set(reportPanelAtom, {
		isOpen: false,
		reportId: null,
		title: null,
		wordCount: null,
		shareToken: null,
		contentType: "markdown",
	});
});

/** Target comment ID to scroll to (from URL navigation or inbox click) */
export const targetCommentIdAtom = atom<number | null>(null);

export const setTargetCommentIdAtom = atom(null, (_, set, commentId: number | null) => {
	set(targetCommentIdAtom, commentId);
});

export const clearTargetCommentIdAtom = atom(null, (_, set) => {
	set(targetCommentIdAtom, null);
});
