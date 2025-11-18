import { atom } from "jotai";

type ActiveChathatUIState = {
	isChatPannelOpen: boolean;
};

export const activeChathatUIAtom = atom<ActiveChathatUIState>({
	isChatPannelOpen: false,
});
export const activeChatIdAtom = atom<string | null>(null);
