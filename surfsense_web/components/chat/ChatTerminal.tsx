"use client";

import { getAnnotationData, type Message } from "@llamaindex/chat-ui";

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
			{/* Pulsing Anchor Icon - uses custom pulse animation for smooth, gentle effect */}
			<svg
				className="w-4 h-4 text-blue-400 animate-anchor-pulse motion-reduce:animate-none"
				viewBox="0 0 24 24"
				fill="currentColor"
				xmlns="http://www.w3.org/2000/svg"
				aria-hidden="true"
			>
				<title>Loading indicator</title>
				{/* Top shackle ring */}
				<circle cx="12" cy="3" r="1.5" />

				{/* Anchor shaft */}
				<rect x="11" y="4" width="2" height="11" rx="0.5" />

				{/* Middle ring/stock */}
				<ellipse cx="12" cy="11" rx="4" ry="1.5" />

				{/* Left fluke */}
				<path d="M 12 15 Q 8 16, 6 19 L 5 19.5 Q 4.5 20, 5 20.5 L 6 21 Q 7 21, 7.5 20 L 9 17.5 Q 10.5 15.5, 12 15 Z" />

				{/* Right fluke */}
				<path d="M 12 15 Q 16 16, 18 19 L 19 19.5 Q 19.5 20, 19 20.5 L 18 21 Q 17 21, 16.5 20 L 15 17.5 Q 13.5 15.5, 12 15 Z" />
			</svg>

			{/* Dynamic Loading Text - subtle and centered */}
			<span className="text-muted-foreground text-sm">{statusText}</span>
		</div>
	);
}
