import { atom } from "jotai";

type ChatUIState = {
	isChatPannelOpen: boolean;
};

export const chatUIAtom = atom<ChatUIState>({
	isChatPannelOpen: false,
});
