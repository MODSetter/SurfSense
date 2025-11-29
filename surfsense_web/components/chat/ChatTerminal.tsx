"use client";

import { getAnnotationData, type Message } from "@llamaindex/chat-ui";
import { Loader2 } from "lucide-react";

// Interface for terminal event information
interface TerminalInfo {
	id: number;
	text: string;
	type: string;
}

// Component props interface
interface TerminalDisplayProps {
	message: Message;
}

// Lookup map for status text based on keywords
// Defined at module scope to avoid recreation on every render
const STATUS_TEXT_MAP: Record<string, string> = {
	research: "Researching...",
	generat: "Generating answer...",
	writ: "Writing response...",
	analyz: "Analyzing...",
	search: "Searching...",
};

/**
 * Loading indicator component that displays a pulsing anchor icon and dynamic status text
 * Respects user's motion preferences and provides proper accessibility support
 * Styled to blend seamlessly with the chat interface
 */
export default function TerminalDisplay({ message }: TerminalDisplayProps) {
	if (!message) {
		return null;
	}

	const events = getAnnotationData(message, "TERMINAL_INFO") as TerminalInfo[];

	// Only show the loading indicator if there are events
	if (events.length === 0) {
		return null;
	}

	// Extract dynamic status text from the last event
	const getStatusText = (): string => {
		const lastEvent = events[events.length - 1];
		const text = lastEvent.text?.toLowerCase() || "";

		// Find matching keyword and return corresponding status text
		for (const [keyword, statusText] of Object.entries(STATUS_TEXT_MAP)) {
			if (text.includes(keyword)) {
				return statusText;
			}
		}

		// Default fallback
		return "Processing...";
	};

	const statusText = getStatusText();

	return (
		<div
			className="flex items-center justify-center gap-2 py-2"
			role="status"
			aria-live="polite"
			aria-label={statusText}
		>
			{/* Loading Spinner - uses Loader2 icon with spin animation */}
			<Loader2
				className="w-4 h-4 text-blue-400 animate-spin motion-reduce:animate-none"
				aria-hidden="true"
			/>

			{/* Dynamic Loading Text - subtle and centered */}
			<span className="text-muted-foreground text-sm">{statusText}</span>
		</div>
	);
}
