"use client";

import { Folder, FolderPlus, Search, X } from "lucide-react";
import { useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { LocalFilesystemBrowser } from "./LocalFilesystemBrowser";

const getFolderDisplayName = (rootPath: string): string =>
	rootPath.split(/[\\/]/).at(-1) || rootPath;

interface DesktopLocalTabContentProps {
	localRootPaths: string[];
	canAddMoreLocalRoots: boolean;
	maxLocalFilesystemRoots: number;
	searchSpaceId: number;
	onPickFilesystemRoot: () => Promise<void> | void;
	onRemoveFilesystemRoot: (rootPath: string) => Promise<void> | void;
	onClearFilesystemRoots: () => Promise<void> | void;
	onOpenLocalFile: (localFilePath: string) => void;
	electronAvailable: boolean;
}

export function DesktopLocalTabContent({
	localRootPaths,
	canAddMoreLocalRoots,
	maxLocalFilesystemRoots,
	searchSpaceId,
	onPickFilesystemRoot,
	onRemoveFilesystemRoot,
	onClearFilesystemRoots,
	onOpenLocalFile,
	electronAvailable,
}: DesktopLocalTabContentProps) {
	const [localSearch, setLocalSearch] = useState("");
	const debouncedLocalSearch = useDebouncedValue(localSearch, 250);
	const localSearchInputRef = useRef<HTMLInputElement>(null);

	return (
		<div className="flex min-h-0 flex-1 flex-col select-none">
			<div className="mx-4 mt-4 mb-3">
				<div className="flex h-7 w-full items-stretch rounded-lg border bg-muted/50 text-[11px] text-muted-foreground">
					{localRootPaths.length > 0 ? (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<button
									type="button"
									className="min-w-0 flex-1 flex items-center gap-1 rounded-l-lg px-2 text-left transition-colors hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
									title={localRootPaths.join("\n")}
									aria-label="Manage selected folders"
								>
									<Folder className="size-3 shrink-0 text-muted-foreground" />
									<span className="truncate">
										{localRootPaths.length === 1
											? "1 folder selected"
											: `${localRootPaths.length} folders selected`}
									</span>
								</button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="start" className="w-56 select-none p-0.5">
								<DropdownMenuLabel className="px-1.5 pt-1.5 pb-0.5 text-xs font-medium text-muted-foreground">
									Selected folders
								</DropdownMenuLabel>
								<DropdownMenuSeparator className="mx-1 my-0.5" />
								{localRootPaths.map((rootPath) => (
									<DropdownMenuItem
										key={rootPath}
										onSelect={(event) => event.preventDefault()}
										className="group h-8 gap-1.5 px-1.5 text-sm text-foreground"
									>
										<Folder className="size-3.5 text-muted-foreground" />
										<span className="min-w-0 flex-1 truncate">
											{getFolderDisplayName(rootPath)}
										</span>
										<button
											type="button"
											className="inline-flex size-5 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground"
											onClick={(event) => {
												event.stopPropagation();
												void onRemoveFilesystemRoot(rootPath);
											}}
											aria-label={`Remove ${getFolderDisplayName(rootPath)}`}
										>
											<X className="size-3" />
										</button>
									</DropdownMenuItem>
								))}
								<DropdownMenuSeparator className="mx-1 my-0.5" />
								<DropdownMenuItem
									variant="destructive"
									className="h-8 px-1.5 text-xs text-destructive focus:text-destructive"
									onClick={() => {
										void onClearFilesystemRoots();
									}}
								>
									Clear all folders
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					) : (
						<div
							className="min-w-0 flex-1 flex items-center gap-1 px-2"
							title="No local folders selected"
						>
							<Folder className="size-3 shrink-0 text-muted-foreground" />
							<span className="truncate">No local folders selected</span>
						</div>
					)}
					<Separator
						orientation="vertical"
						className="data-[orientation=vertical]:h-3 self-center bg-border"
					/>
					{electronAvailable ? (
						<Tooltip>
							<TooltipTrigger asChild>
								<span className="inline-flex">
									<button
										type="button"
										className="flex w-8 items-center justify-center rounded-r-lg text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50"
										onClick={() => {
											void onPickFilesystemRoot();
										}}
										disabled={!canAddMoreLocalRoots}
										aria-label="Add folder"
									>
										<FolderPlus className="size-3.5" />
									</button>
								</span>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs">
								{canAddMoreLocalRoots
									? "Add folder"
									: `You can add up to ${maxLocalFilesystemRoots} folders`}
							</TooltipContent>
						</Tooltip>
					) : null}
				</div>
			</div>
			<div className="mx-4 mb-2">
				<div className="relative flex-1 min-w-0">
					<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
						<Search size={13} aria-hidden="true" />
					</div>
					<Input
						ref={localSearchInputRef}
						className="peer h-8 w-full pl-8 pr-8 text-sm bg-sidebar border-border/60 select-none focus:select-text"
						value={localSearch}
						onChange={(e) => setLocalSearch(e.target.value)}
						placeholder="Search local files"
						type="text"
						aria-label="Search local files"
					/>
					{Boolean(localSearch) && (
						<button
							type="button"
							className="absolute inset-y-0 right-0 flex h-full w-8 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground transition-colors"
							aria-label="Clear local search"
							onClick={() => {
								setLocalSearch("");
								localSearchInputRef.current?.focus();
							}}
						>
							<X size={13} strokeWidth={2} aria-hidden="true" />
						</button>
					)}
				</div>
			</div>
			<LocalFilesystemBrowser
				rootPaths={localRootPaths}
				searchSpaceId={searchSpaceId}
				active
				searchQuery={debouncedLocalSearch.trim() || undefined}
				onOpenFile={onOpenLocalFile}
			/>
		</div>
	);
}
