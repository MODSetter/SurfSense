"use client";

import type React from "react";
import { useState } from "react";
import { SheetTrigger } from "@/components/ui/sheet";
import { SourceDetailSheet } from "./SourceDetailSheet";

export const CitationDisplay: React.FC<{ index: number; node: any }> = ({ index, node }) => {
	const chunkId = Number(node?.id);
	const sourceType = node?.metadata?.source_type;
	const [isOpen, setIsOpen] = useState(false);

	return (
		<SourceDetailSheet
			open={isOpen}
			onOpenChange={setIsOpen}
			chunkId={chunkId}
			sourceType={sourceType}
			title={node?.metadata?.title || node?.metadata?.group_name || "Source"}
			description={node?.text}
			url={node?.url}
		>
			<SheetTrigger asChild>
				<span className="text-[10px] font-bold bg-slate-500 hover:bg-slate-600 text-white rounded-full w-4 h-4 inline-flex items-center justify-center align-super cursor-pointer transition-colors">
					{index + 1}
				</span>
			</SheetTrigger>
		</SourceDetailSheet>
	);
};
