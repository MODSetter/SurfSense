import { atom } from "jotai";

interface ActionLogDialogState {
	open: boolean;
	threadId: number | null;
}

export const actionLogDialogAtom = atom<ActionLogDialogState>({
	open: false,
	threadId: null,
});

export const openActionLogDialogAtom = atom(null, (_get, set, threadId: number) => {
	set(actionLogDialogAtom, { open: true, threadId });
});

export const closeActionLogDialogAtom = atom(null, (_get, set) => {
	set(actionLogDialogAtom, { open: false, threadId: null });
});
