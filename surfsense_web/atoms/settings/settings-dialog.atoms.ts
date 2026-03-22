import { atom } from "jotai";

export interface SearchSpaceSettingsDialogState {
	open: boolean;
	initialTab: string;
}

export interface UserSettingsDialogState {
	open: boolean;
	initialTab: string;
}

export const searchSpaceSettingsDialogAtom = atom<SearchSpaceSettingsDialogState>({
	open: false,
	initialTab: "general",
});

export const userSettingsDialogAtom = atom<UserSettingsDialogState>({
	open: false,
	initialTab: "profile",
});

export const teamDialogAtom = atom<boolean>(false);

export const morePagesDialogAtom = atom<boolean>(false);
