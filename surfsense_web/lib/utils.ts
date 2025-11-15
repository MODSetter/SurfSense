import type { Message } from "@ai-sdk/react";
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export function getChatTitleFromMessages(messages: Message[]) {
	const userMessages = messages.filter((msg) => msg.role === "user");
	if (userMessages.length === 0) return "Untitled Chat";
	return userMessages[0].content;
}
