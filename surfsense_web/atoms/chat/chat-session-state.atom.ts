"use client";

import { atom } from "jotai";

export interface ChatSessionStateData {
	threadId: number;
	isAiResponding: boolean;
	respondingToUserId: string | null;
}

/**
 * Global chat session state atom.
 * Updated by useChatSessionStateSync hook, read anywhere.
 */
export const chatSessionStateAtom = atom<ChatSessionStateData | null>(null);
