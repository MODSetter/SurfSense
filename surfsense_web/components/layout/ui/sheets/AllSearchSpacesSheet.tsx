"use client";

import { Calendar, MoreHorizontal, Search, Settings, Share2, Trash2, UserCheck, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import type { SearchSpace } from "../../types/layout.types";

function formatDate(dateString: string): string {
	return new Date(dateString).toLocaleDateString("en-US", {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

interface AllSearchSpacesSheetProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaces: SearchSpace[];
	onSearchSpaceSelect: (id: number) => void;
	onCreateNew?: () => void;
	onSettings?: (id: number) => void;
	onDelete?: (id: number) => void;
}

export function AllSearchSpacesSheet({
	open,
	onOpenChange,
	searchSpaces,
	onSearchSpaceSelect,
	onCreateNew,
	onSettings,
	onDelete,
}: AllSearchSpacesSheetProps) {
	const t = useTranslations("searchSpace");
	const tCommon = useTranslations("common");

	const [spaceToDelete, setSpaceToDelete] = useState<SearchSpace | null>(null);

	const handleSelect = (id: number) => {
		onSearchSpaceSelect(id);
		onOpenChange(false);
	};

	const handleSettings = (e: React.MouseEvent, space: SearchSpace) => {
		e.stopPropagation();
		onOpenChange(false);
		onSettings?.(space.id);
	};

	const handleDeleteClick = (e: React.MouseEvent, space: SearchSpace) => {
		e.stopPropagation();
		setSpaceToDelete(space);
	};

	const confirmDelete = () => {
		if (spaceToDelete) {
			onDelete?.(spaceToDelete.id);
			setSpaceToDelete(null);
		}
	};

	return (
		<>
			<Sheet open={open} onOpenChange={onOpenChange}>
				<SheetContent side="right" className="w-full sm:max-w-md">
					<SheetHeader>
						<div className="flex items-center gap-3">
							<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
								<Search className="h-5 w-5 text-primary" />
							</div>
							<div className="flex flex-col gap-0.5">
								<SheetTitle>{t("all_search_spaces")}</SheetTitle>
								<SheetDescription>
									{t("search_spaces_count", { count: searchSpaces.length })}
								</SheetDescription>
							</div>
						</div>
					</SheetHeader>

					<div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
						{searchSpaces.length === 0 ? (
							<div className="flex flex-1 flex-col items-center justify-center gap-4 py-12 text-center">
								<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
									<Search className="h-8 w-8 text-muted-foreground" />
								</div>
								<div className="flex flex-col gap-1">
									<p className="font-medium">{t("no_search_spaces")}</p>
									<p className="text-sm text-muted-foreground">
										{t("create_first_search_space")}
									</p>
								</div>
								{onCreateNew && (
									<Button onClick={onCreateNew} className="mt-2">
										{t("create_button")}
									</Button>
								)}
							</div>
						) : (
							searchSpaces.map((space) => (
								<button
									key={space.id}
									type="button"
									onClick={() => handleSelect(space.id)}
									className="flex w-full flex-col gap-2 rounded-lg border p-4 text-left transition-colors hover:bg-accent hover:border-accent-foreground/20"
								>
									<div className="flex items-start justify-between gap-2">
										<div className="flex flex-1 flex-col gap-1">
											<span className="font-medium leading-tight">
												{space.name}
											</span>
											{space.description && (
												<span className="text-sm text-muted-foreground line-clamp-2">
													{space.description}
												</span>
											)}
										</div>

										<div className="flex shrink-0 items-center gap-2">
										{space.memberCount > 1 && (
											<Badge variant="outline" className="shrink-0">
												<Share2 className="mr-1 h-3 w-3" />
												{tCommon("shared")}
											</Badge>
										)}

										{space.isOwner && (
											<DropdownMenu>
												<DropdownMenuTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className="h-6 w-6 shrink-0"
														onClick={(e) => e.stopPropagation()}
													>
														<MoreHorizontal className="h-4 w-4" />
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end">
													<DropdownMenuItem onClick={(e) => handleSettings(e, space)}>
														<Settings className="mr-2 h-4 w-4" />
														{tCommon("settings")}
													</DropdownMenuItem>
													<DropdownMenuSeparator />
													<DropdownMenuItem
														onClick={(e) => handleDeleteClick(e, space)}
														className="text-destructive focus:text-destructive"
													>
														<Trash2 className="mr-2 h-4 w-4" />
														{tCommon("delete")}
													</DropdownMenuItem>
												</DropdownMenuContent>
											</DropdownMenu>
										)}
									</div>
									</div>

									<div className="flex items-center gap-4 text-xs text-muted-foreground">
										<span className="flex items-center gap-1">
											{space.isOwner ? (
												<UserCheck className="h-3.5 w-3.5" />
											) : (
												<Users className="h-3.5 w-3.5" />
											)}
											{t("members_count", { count: space.memberCount })}
										</span>
										{space.createdAt && (
											<span className="flex items-center gap-1">
												<Calendar className="h-3.5 w-3.5" />
												{formatDate(space.createdAt)}
											</span>
										)}
									</div>
								</button>
							))
						)}
					</div>

					{searchSpaces.length > 0 && onCreateNew && (
						<div className="border-t p-4">
							<Button onClick={onCreateNew} variant="outline" className="w-full">
								{t("create_new_search_space")}
							</Button>
						</div>
					)}
				</SheetContent>
			</Sheet>

			<AlertDialog open={!!spaceToDelete} onOpenChange={(open) => !open && setSpaceToDelete(null)}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>{t("delete_title")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("delete_confirm", { name: spaceToDelete?.name })}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
						<AlertDialogAction
							onClick={confirmDelete}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							{tCommon("delete")}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</>
	);
}
