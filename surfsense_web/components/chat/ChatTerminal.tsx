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

/**
 * Loading indicator component that displays a rotating anchor icon and dynamic status text
 * Respects user's motion preferences and provides proper accessibility support
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
		if (events.length === 0) return "Processing...";

		const lastEvent = events[events.length - 1];
		const text = lastEvent.text?.toLowerCase() || "";

		// Match common process stages and return appropriate text
		if (text.includes("research")) {
			return "Researching...";
		}
		if (text.includes("generat")) {
			return "Generating answer...";
		}
		if (text.includes("writ")) {
			return "Writing response...";
		}
		if (text.includes("analyz")) {
			return "Analyzing...";
		}
		if (text.includes("search")) {
			return "Searching...";
		}

		// Default fallback
		return "Processing...";
	};

	const statusText = getStatusText();

	return (
		<div
			className="flex items-center gap-3 py-3 px-4 bg-gray-900 rounded-lg border border-gray-700"
			role="status"
			aria-live="polite"
			aria-label={statusText}
		>
			{/* Rotating Anchor Icon */}
			<svg
				className="w-5 h-5 text-blue-400 animate-spin-slow motion-reduce:animate-none"
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

			{/* Dynamic Loading Text */}
			<span className="text-gray-300 text-sm">{statusText}</span>
		</div>
	);
}
