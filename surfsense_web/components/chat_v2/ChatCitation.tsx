"use client";

import React from "react";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { ExternalLink } from "lucide-react";

export const CitationDisplay: React.FC<{ index: number; node: any }> = ({
	index,
	node,
}) => {
	const truncateText = (text: string, maxLength: number = 200) => {
		if (text.length <= maxLength) return text;
		return text.substring(0, maxLength) + "...";
	};

	const handleUrlClick = (e: React.MouseEvent, url: string) => {
		e.preventDefault();
		e.stopPropagation();
		window.open(url, "_blank", "noopener,noreferrer");
	};

	return (
		<Popover>
			<PopoverTrigger asChild>
				<span className="text-[10px] font-bold bg-slate-500 hover:bg-slate-600 text-white rounded-full w-4 h-4 inline-flex items-center justify-center align-super cursor-pointer transition-colors">
					{index + 1}
				</span>
			</PopoverTrigger>
			<PopoverContent className="w-80 p-4 space-y-3 relative" align="start">
				{/* External Link Button - Top Right */}
				{node?.url && (
					<button
						onClick={(e) => handleUrlClick(e, node.url)}
						className="absolute top-3 right-3 inline-flex items-center justify-center w-6 h-6 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
						title="Open in new tab"
					>
						<ExternalLink size={14} />
					</button>
				)}

				{/* Heading */}
				<div className="text-sm font-semibold text-slate-900 dark:text-slate-100 pr-8">
					{node?.metadata?.group_name || "Source"}
				</div>

				{/* Source */}
				<div className="text-xs text-slate-600 dark:text-slate-400 font-medium">
					{node?.metadata?.title || "Untitled"}
				</div>

				{/* Body */}
				<div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
					{truncateText(node?.text || "No content available")}
				</div>
			</PopoverContent>
		</Popover>
	);
};
