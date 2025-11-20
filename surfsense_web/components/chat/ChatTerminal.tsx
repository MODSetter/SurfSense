"use client";

import { getAnnotationData, type Message } from "@llamaindex/chat-ui";

export default function TerminalDisplay({ message }: { message: Message; open: boolean }) {
	if (!message) {
		return null;
	}

	interface TerminalInfo {
		id: number;
		text: string;
		type: string;
	}

	const events = getAnnotationData(message, "TERMINAL_INFO") as TerminalInfo[];

	// Only show the loading indicator if there are events
	if (events.length === 0) {
		return null;
	}

	return (
		<div className="flex items-center gap-3 py-3 px-4 bg-gray-900 rounded-lg border border-gray-700">
			{/* Rotating Anchor Icon */}
			<svg
				className="w-5 h-5 text-blue-400 animate-spin-slow"
				viewBox="0 0 24 24"
				fill="currentColor"
				xmlns="http://www.w3.org/2000/svg"
			>
				<title>Loading</title>
				<path d="M12 2C12.5523 2 13 2.44772 13 3V6C13 6.55228 12.5523 7 12 7C11.4477 7 11 6.55228 11 6V3C11 2.44772 11.4477 2 12 2Z" />
				<path d="M12 10C13.1046 10 14 10.8954 14 12C14 13.1046 13.1046 14 12 14C10.8954 14 10 13.1046 10 12C10 10.8954 10.8954 10 12 10Z" />
				<path d="M8 12C8 10.8954 8.89543 10 10 10V14C8.89543 14 8 13.1046 8 12Z" />
				<path d="M14 12C14 13.1046 14.8954 14 16 14V10C14.8954 10 14 10.8954 14 12Z" />
				<path d="M12 14C12.5523 14 13 14.4477 13 15V17L15.5 19.5C15.8905 19.8905 15.8905 20.5237 15.5 20.9142C15.1095 21.3047 14.4763 21.3047 14.0858 20.9142L12 18.8284L9.91421 20.9142C9.52369 21.3047 8.89052 21.3047 8.5 20.9142C8.10948 20.5237 8.10948 19.8905 8.5 19.5L11 17V15C11 14.4477 11.4477 14 12 14Z" />
			</svg>

			{/* Loading Text */}
			<span className="text-gray-300 text-sm">Generating answer...</span>
		</div>
	);
}
