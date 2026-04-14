import { atom } from "jotai";

export interface SelectedFolder {
	path: string;
	name: string;
}

// Atom to control the folder watch dialog open state
export const folderWatchDialogOpenAtom = atom(false);

// Atom to store initial folder selection for the dialog
export const folderWatchInitialFolderAtom = atom<SelectedFolder | null>(null);
