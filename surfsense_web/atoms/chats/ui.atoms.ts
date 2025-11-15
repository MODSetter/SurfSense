import { atom } from "jotai";

type ActiveChathatUIState = {
	isChatPannelOpen: boolean;
};

export const activeChathatUIAtom = atom<ActiveChathatUIState>({
	isChatPannelOpen: false,
});
