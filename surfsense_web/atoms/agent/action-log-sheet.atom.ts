import { atom } from "jotai";

interface ActionLogSheetState {
	open: boolean;
	threadId: number | null;
}

export const actionLogSheetAtom = atom<ActionLogSheetState>({
	open: false,
	threadId: null,
});

export const openActionLogSheetAtom = atom(null, (_get, set, threadId: number) => {
	set(actionLogSheetAtom, { open: true, threadId });
});

export const closeActionLogSheetAtom = atom(null, (_get, set) => {
	set(actionLogSheetAtom, { open: false, threadId: null });
});
