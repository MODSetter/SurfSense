"use client";

import { CircleAlert, CircleX, Columns3, Filter, ListFilter, Trash } from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useTranslations } from "next-intl";
import React, { useMemo, useRef } from "react";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ColumnVisibility } from "./types";

const fadeInScale: Variants = {
	hidden: { opacity: 0, scale: 0.95 },
	visible: { opacity: 1, scale: 1, transition: { type: "spring", stiffness: 300, damping: 30 } },
	exit: { opacity: 0, scale: 0.95, transition: { duration: 0.15 } },
};

export function DocumentsFilters({
	typeCounts: typeCountsRecord,
	selectedIds,
	onSearch,
	searchValue,
	onBulkDelete,
	onToggleType,
	activeTypes,
	columnVisibility,
	onToggleColumn,
}: {
	typeCounts: Record<string, number>;
	selectedIds: Set<number>;
	onSearch: (v: string) => void;
	searchValue: string;
	onBulkDelete: () => Promise<void>;
	onToggleType: (type: string, checked: boolean) => void;
	activeTypes: string[];
	columnVisibility: ColumnVisibility;
	onToggleColumn: (id: keyof ColumnVisibility, checked: boolean) => void;
}) {
	const t = useTranslations("documents");
	const id = React.useId();
	const inputRef = useRef<HTMLInputElement>(null);

	const uniqueTypes = useMemo(() => {
		return Object.keys(typeCountsRecord).sort();
	}, [typeCountsRecord]);

	const typeCounts = useMemo(() => {
		const map = new Map<string, number>();
		for (const [type, count] of Object.entries(typeCountsRecord)) {
			map.set(type, count);
		}
		return map;
	}, [typeCountsRecord]);

	return (
		<motion.div
			className="flex flex-wrap items-center justify-between gap-3"
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.1 }}
		>
			<div className="flex items-center gap-3">
				<motion.div
					className="relative"
					initial={{ opacity: 0, y: -10 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ type: "spring", stiffness: 300, damping: 30 }}
				>
					<Input
						id={`${id}-input`}
						ref={inputRef}
						className="peer min-w-60 ps-9"
						value={searchValue}
						onChange={(e) => onSearch(e.target.value)}
						placeholder={t("filter_placeholder")}
						type="text"
						aria-label={t("filter_placeholder")}
					/>
					<motion.div
						className="pointer-events-none absolute inset-y-0 start-0 flex items-center justify-center ps-3 text-muted-foreground/80 peer-disabled:opacity-50"
						initial={{ scale: 0.8 }}
						animate={{ scale: 1 }}
						transition={{ delay: 0.1 }}
					>
						<ListFilter size={16} strokeWidth={2} aria-hidden="true" />
					</motion.div>
					{Boolean(searchValue) && (
						<motion.button
							className="absolute inset-y-0 end-0 flex h-full w-9 items-center justify-center rounded-e-lg text-muted-foreground/80 outline-offset-2 transition-colors hover:text-foreground focus:z-10 focus-visible:outline focus-visible:outline-ring/70"
							aria-label="Clear filter"
							onClick={() => {
								onSearch("");
								inputRef.current?.focus();
							}}
							initial={{ opacity: 0, rotate: -90 }}
							animate={{ opacity: 1, rotate: 0 }}
							exit={{ opacity: 0, rotate: 90 }}
							whileHover={{ scale: 1.1 }}
							whileTap={{ scale: 0.9 }}
						>
							<CircleX size={16} strokeWidth={2} aria-hidden="true" />
						</motion.button>
					)}
				</motion.div>

				<Popover>
					<PopoverTrigger asChild>
						<motion.div
							whileHover={{ scale: 1.05 }}
							whileTap={{ scale: 0.95 }}
							transition={{ type: "spring", stiffness: 400, damping: 17 }}
						>
							<Button variant="outline">
								<Filter
									className="-ms-1 me-2 opacity-60"
									size={16}
									strokeWidth={2}
									aria-hidden="true"
								/>
								Type
								{activeTypes.length > 0 && (
									<motion.span
										initial={{ scale: 0.8 }}
										animate={{ scale: 1 }}
										className="-me-1 ms-3 inline-flex h-5 max-h-full items-center rounded border border-border bg-background px-1 text-[0.625rem] font-medium text-muted-foreground/70"
									>
										{activeTypes.length}
									</motion.span>
								)}
							</Button>
						</motion.div>
					</PopoverTrigger>
					<PopoverContent className="min-w-36 p-3" align="start">
						<motion.div initial="hidden" animate="visible" exit="exit" variants={fadeInScale}>
							<div className="space-y-3">
								<div className="text-xs font-medium text-muted-foreground">Filters</div>
								<div className="space-y-3">
									<AnimatePresence>
										{uniqueTypes.map((value, i) => (
											<motion.div
												key={value}
												className="flex items-center gap-2"
												initial={{ opacity: 0, y: -5 }}
												animate={{ opacity: 1, y: 0 }}
												exit={{ opacity: 0, y: 5 }}
												transition={{ delay: i * 0.05 }}
											>
												<Checkbox
													id={`${id}-${i}`}
													checked={activeTypes.includes(value)}
													onCheckedChange={(checked: boolean) => onToggleType(value, !!checked)}
												/>
												<Label
													htmlFor={`${id}-${i}`}
													className="flex grow justify-between gap-2 font-normal"
												>
													{value}{" "}
													<span className="ms-2 text-xs text-muted-foreground">
														{typeCounts.get(value)}
													</span>
												</Label>
											</motion.div>
										))}
									</AnimatePresence>
								</div>
							</div>
						</motion.div>
					</PopoverContent>
				</Popover>

				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<motion.div
							whileHover={{ scale: 1.05 }}
							whileTap={{ scale: 0.95 }}
							transition={{ type: "spring", stiffness: 400, damping: 17 }}
						>
							<Button variant="outline">
								<Columns3
									className="-ms-1 me-2 opacity-60"
									size={16}
									strokeWidth={2}
									aria-hidden="true"
								/>
								View
							</Button>
						</motion.div>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						<DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
						{(
							[
								["title", "Title"],
								["document_type", "Type"],
								["content", "Content"],
								["created_at", "Created At"],
							] as Array<[keyof ColumnVisibility, string]>
						).map(([key, label]) => (
							<DropdownMenuCheckboxItem
								key={key}
								className="capitalize"
								checked={columnVisibility[key]}
								onCheckedChange={(v) => onToggleColumn(key, !!v)}
								onSelect={(e) => e.preventDefault()}
							>
								{label}
							</DropdownMenuCheckboxItem>
						))}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>

			<div className="flex items-center gap-3">
				{selectedIds.size > 0 && (
					<AlertDialog>
						<AlertDialogTrigger asChild>
							<Button className="ml-auto" variant="outline">
								<Trash
									className="-ms-1 me-2 opacity-60"
									size={16}
									strokeWidth={2}
									aria-hidden="true"
								/>
								Delete
								<span className="-me-1 ms-3 inline-flex h-5 max-h-full items-center rounded border border-border bg-background px-1 text-[0.625rem] font-medium text-muted-foreground/70">
									{selectedIds.size}
								</span>
							</Button>
						</AlertDialogTrigger>
						<AlertDialogContent>
							<div className="flex flex-col gap-2 max-sm:items-center sm:flex-row sm:gap-4">
								<div
									className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border"
									aria-hidden="true"
								>
									<CircleAlert className="opacity-80" size={16} strokeWidth={2} />
								</div>
								<AlertDialogHeader>
									<AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
									<AlertDialogDescription>
										This action cannot be undone. This will permanently delete {selectedIds.size}{" "}
										selected {selectedIds.size === 1 ? "row" : "rows"}.
									</AlertDialogDescription>
								</AlertDialogHeader>
							</div>
							<AlertDialogFooter>
								<AlertDialogCancel>Cancel</AlertDialogCancel>
								<AlertDialogAction onClick={onBulkDelete}>Delete</AlertDialogAction>
							</AlertDialogFooter>
						</AlertDialogContent>
					</AlertDialog>
				)}
			</div>
		</motion.div>
	);
}
