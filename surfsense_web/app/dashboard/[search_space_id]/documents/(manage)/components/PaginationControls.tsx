"use client";

import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";

const PAGE_SIZE = 50;

export function PaginationControls({
	pageIndex,
	total,
	onFirst,
	onPrev,
	onNext,
	onLast,
	canPrev,
	canNext,
}: {
	pageIndex: number;
	total: number;
	onFirst: () => void;
	onPrev: () => void;
	onNext: () => void;
	onLast: () => void;
	canPrev: boolean;
	canNext: boolean;
}) {
	const start = pageIndex * PAGE_SIZE + 1;
	const end = Math.min((pageIndex + 1) * PAGE_SIZE, total);

	return (
		<motion.div
			className="flex items-center justify-end gap-3 py-3 px-2 select-none"
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.3 }}
		>
			{/* Range indicator */}
			<span className="text-sm text-muted-foreground tabular-nums">
				{start}-{end} of {total}
			</span>

			{/* Navigation buttons */}
			<div className="flex items-center gap-1">
				<Button
					variant="ghost"
					size="icon"
					className="h-8 w-8 disabled:opacity-40"
					onClick={onFirst}
					disabled={!canPrev}
					aria-label="Go to first page"
				>
					<ChevronFirst size={18} strokeWidth={2} />
				</Button>
				<Button
					variant="ghost"
					size="icon"
					className="h-8 w-8 disabled:opacity-40"
					onClick={onPrev}
					disabled={!canPrev}
					aria-label="Go to previous page"
				>
					<ChevronLeft size={18} strokeWidth={2} />
				</Button>
				<Button
					variant="ghost"
					size="icon"
					className="h-8 w-8 disabled:opacity-40"
					onClick={onNext}
					disabled={!canNext}
					aria-label="Go to next page"
				>
					<ChevronRight size={18} strokeWidth={2} />
				</Button>
				<Button
					variant="ghost"
					size="icon"
					className="h-8 w-8 disabled:opacity-40"
					onClick={onLast}
					disabled={!canNext}
					aria-label="Go to last page"
				>
					<ChevronLast size={18} strokeWidth={2} />
				</Button>
			</div>
		</motion.div>
	);
}

export { PAGE_SIZE };
