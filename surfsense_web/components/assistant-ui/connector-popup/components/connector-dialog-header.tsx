"use client";

import { Search, X } from "lucide-react";
import type { FC } from "react";
import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface ConnectorDialogHeaderProps {
	activeTab: string;
	totalSourceCount: number;
	searchQuery: string;
	onTabChange: (value: string) => void;
	onSearchChange: (query: string) => void;
	isScrolled: boolean;
}

export const ConnectorDialogHeader: FC<ConnectorDialogHeaderProps> = ({
	totalSourceCount,
	searchQuery,
	onSearchChange,
	isScrolled,
}) => {
	return (
		<div
			className={cn(
				"flex-shrink-0 px-4 sm:px-12 pt-5 sm:pt-10 transition-shadow duration-200 relative z-10",
				isScrolled && "shadow-xl bg-muted/50 backdrop-blur-md"
			)}
		>
			<DialogHeader>
				<DialogTitle className="text-xl sm:text-3xl font-semibold tracking-tight">
					Connectors
				</DialogTitle>
				<DialogDescription className="text-xs sm:text-base text-muted-foreground/80 mt-1 sm:mt-1.5">
					Search across all your apps and data in one place.
				</DialogDescription>
			</DialogHeader>

			<div className="flex flex-col-reverse sm:flex-row sm:items-end justify-between gap-4 sm:gap-8 mt-4 sm:mt-8 border-b border-border/80 dark:border-white/5">
				<TabsList className="bg-transparent p-0 gap-4 sm:gap-8 h-auto w-full sm:w-auto justify-center sm:justify-start">
					<TabsTrigger
						value="all"
						className="px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white transition-all text-base font-medium text-muted-foreground data-[state=active]:text-foreground"
					>
						All Connectors
					</TabsTrigger>
					<TabsTrigger
						value="active"
						className="group px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent transition-all text-base font-medium flex items-center gap-2 text-muted-foreground data-[state=active]:text-foreground relative"
					>
						<span className="relative">
							Active
							<span className="absolute bottom-[-13.5px] left-1/2 -translate-x-1/2 w-12 h-[1.5px] bg-foreground dark:bg-white opacity-0 group-data-[state=active]:opacity-100 transition-all duration-200" />
						</span>
						{totalSourceCount > 0 && (
							<span className="px-1.5 py-0.5 rounded-full bg-muted-foreground/15 text-[10px] font-bold">
								{totalSourceCount}
							</span>
						)}
					</TabsTrigger>
				</TabsList>

				<div className="w-full sm:w-72 sm:pb-1">
					<div className="relative">
						<Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-500 dark:text-gray-500" />
						<input
							type="text"
							placeholder="Search"
							className={cn(
								"w-full bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 focus:bg-slate-400/10 dark:focus:bg-white/10 border border-border rounded-xl pl-9 py-2 text-sm transition-all outline-none placeholder:text-muted-foreground/50",
								searchQuery ? "pr-9" : "pr-4"
							)}
							value={searchQuery}
							onChange={(e) => onSearchChange(e.target.value)}
						/>
						{searchQuery && (
							<button
								type="button"
								onClick={() => onSearchChange("")}
								className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
								aria-label="Clear search"
							>
								<X className="size-4" />
							</button>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};
