import { atom } from "jotai";
import type { GetChatsRequest } from "@/contracts/types/chat.types";

type ActiveChathatUIState = {
	isChatPannelOpen: boolean;
};

export const activeChathatUIAtom = atom<ActiveChathatUIState>({
	isChatPannelOpen: false,
});

export const activeChatIdAtom = atom<string | null>(null);

export const globalChatsQueryParamsAtom = atom<GetChatsRequest["queryParams"]>({
	limit: 5,
	skip: 0,
});
