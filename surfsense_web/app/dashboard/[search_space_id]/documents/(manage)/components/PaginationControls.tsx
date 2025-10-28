"use client";

import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Pagination, PaginationContent, PaginationItem } from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export function PaginationControls({
	pageIndex,
	pageSize,
	total,
	onPageSizeChange,
	onFirst,
	onPrev,
	onNext,
	onLast,
	canPrev,
	canNext,
	id,
}: {
	pageIndex: number;
	pageSize: number;
	total: number;
	onPageSizeChange: (size: number) => void;
	onFirst: () => void;
	onPrev: () => void;
	onNext: () => void;
	onLast: () => void;
	canPrev: boolean;
	canNext: boolean;
	id: string;
}) {
	const t = useTranslations("documents");
	const start = total === 0 ? 0 : pageIndex * pageSize + 1;
	const end = Math.min((pageIndex + 1) * pageSize, total);

	return (
		<div className="flex items-center justify-between gap-8 mt-6">
			<motion.div
				className="flex items-center gap-3"
				initial={{ opacity: 0, x: -20 }}
				animate={{ opacity: 1, x: 0 }}
				transition={{ type: "spring", stiffness: 300, damping: 30 }}
			>
				<Label htmlFor={id} className="max-sm:sr-only">
					{t("rows_per_page")}
				</Label>
				<Select value={String(pageSize)} onValueChange={(v) => onPageSizeChange(Number(v))}>
					<SelectTrigger id={id} className="w-fit whitespace-nowrap">
						<SelectValue placeholder="Select number of results" />
					</SelectTrigger>
					<SelectContent>
						{[5, 10, 25, 50].map((s) => (
							<SelectItem key={s} value={String(s)}>
								{s}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</motion.div>

			<motion.div
				className="flex grow justify-end whitespace-nowrap text-sm text-muted-foreground"
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ delay: 0.2 }}
			>
				<p className="whitespace-nowrap text-sm text-muted-foreground" aria-live="polite">
					<span className="text-foreground">
						{start}-{end}
					</span>{" "}
					of <span className="text-foreground">{total}</span>
				</p>
			</motion.div>

			<div>
				<Pagination>
					<PaginationContent>
						<PaginationItem>
							<motion.div
								whileHover={{ scale: 1.05 }}
								whileTap={{ scale: 0.95 }}
								transition={{ type: "spring", stiffness: 400, damping: 17 }}
							>
								<Button
									size="icon"
									variant="outline"
									className="disabled:pointer-events-none disabled:opacity-50"
									onClick={onFirst}
									disabled={!canPrev}
									aria-label="Go to first page"
								>
									<ChevronFirst size={16} strokeWidth={2} aria-hidden="true" />
								</Button>
							</motion.div>
						</PaginationItem>
						<PaginationItem>
							<motion.div
								whileHover={{ scale: 1.05 }}
								whileTap={{ scale: 0.95 }}
								transition={{ type: "spring", stiffness: 400, damping: 17 }}
							>
								<Button
									size="icon"
									variant="outline"
									className="disabled:pointer-events-none disabled:opacity-50"
									onClick={onPrev}
									disabled={!canPrev}
									aria-label="Go to previous page"
								>
									<ChevronLeft size={16} strokeWidth={2} aria-hidden="true" />
								</Button>
							</motion.div>
						</PaginationItem>
						<PaginationItem>
							<motion.div
								whileHover={{ scale: 1.05 }}
								whileTap={{ scale: 0.95 }}
								transition={{ type: "spring", stiffness: 400, damping: 17 }}
							>
								<Button
									size="icon"
									variant="outline"
									className="disabled:pointer-events-none disabled:opacity-50"
									onClick={onNext}
									disabled={!canNext}
									aria-label="Go to next page"
								>
									<ChevronRight size={16} strokeWidth={2} aria-hidden="true" />
								</Button>
							</motion.div>
						</PaginationItem>
						<PaginationItem>
							<motion.div
								whileHover={{ scale: 1.05 }}
								whileTap={{ scale: 0.95 }}
								transition={{ type: "spring", stiffness: 400, damping: 17 }}
							>
								<Button
									size="icon"
									variant="outline"
									className="disabled:pointer-events-none disabled:opacity-50"
									onClick={onLast}
									disabled={!canNext}
									aria-label="Go to last page"
								>
									<ChevronLast size={16} strokeWidth={2} aria-hidden="true" />
								</Button>
							</motion.div>
						</PaginationItem>
					</PaginationContent>
				</Pagination>
			</div>
		</div>
	);
}
