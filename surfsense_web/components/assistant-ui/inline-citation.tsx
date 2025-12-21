"use client";

import type { FC } from "react";
import { useState } from "react";
import { SheetTrigger } from "@/components/ui/sheet";
import { SourceDetailSheet } from "@/components/chat/SourceDetailSheet";

interface InlineCitationProps {
	chunkId: number;
}

/**
 * Inline citation component for the new chat.
 * Renders a clickable badge that opens the SourceDetailSheet with document chunk details.
 */
export const InlineCitation: FC<InlineCitationProps> = ({ chunkId }) => {
	const [isOpen, setIsOpen] = useState(false);

	return (
		<SourceDetailSheet
			open={isOpen}
			onOpenChange={setIsOpen}
			chunkId={chunkId}
			sourceType=""
			title="Source"
			description=""
			url=""
		>
			<SheetTrigger asChild>
				<span
					className="text-[10px] font-bold bg-primary/80 hover:bg-primary text-primary-foreground rounded-full w-4 h-4 inline-flex items-center justify-center align-super cursor-pointer transition-colors ml-0.5"
					title={`View source (chunk ${chunkId})`}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						className="w-2.5 h-2.5"
					>
						<path d="M6.22 8.72a.75.75 0 0 0 1.06 1.06l5.22-5.22v1.69a.75.75 0 0 0 1.5 0v-3.5a.75.75 0 0 0-.75-.75h-3.5a.75.75 0 0 0 0 1.5h1.69L6.22 8.72Z" />
						<path d="M3.5 6.75c0-.69.56-1.25 1.25-1.25H7A.75.75 0 0 0 7 4H4.75A2.75 2.75 0 0 0 2 6.75v4.5A2.75 2.75 0 0 0 4.75 14h4.5A2.75 2.75 0 0 0 12 11.25V9a.75.75 0 0 0-1.5 0v2.25c0 .69-.56 1.25-1.25 1.25h-4.5c-.69 0-1.25-.56-1.25-1.25v-4.5Z" />
					</svg>
				</span>
			</SheetTrigger>
		</SourceDetailSheet>
	);
};
